"""A genotype pasted out of a VCF is refused; nobody was saying it is allele *indices* (RM77).

`GT` is `0/1` and `genotype` wants the bases, and pasting the `GT` field is the obvious first guess —
which makes it the single most likely mistake an author makes in this column. Before this, `0/1` fell
through to the nucleotide-grammar wall, a sentence reciting what an allele may be (nucleotides, `*`, a
symbolic token whose first-level type is one of five) that never mentions the one thing that resolves
the cell: those digits index the record's own REF/ALT list, and this column spells the alleles out.

`0/1/1` was **worse**, and it got worse in 0.6. The ploidy-message fix gave it a confident, correct
explanation of the two-allele ceiling — about the wrong thing, since that cell's defect is the notation
and not how many alleles it names. A correct sentence aimed at the wrong defect sends the author to
change the wrong cell, which is why the diagnosis here runs *ahead* of the arity branch.

This is CLAUDE.md's standing class — a generic rejection is a dead end where a specific one is a fix —
and the repair is the shape `reject_reserved` / `reject_authority_keys` / `reject_misplaced` already
share: a message that **changes no verdict**. Every cell below was refused before and is refused now.

The second half of RM77 is at the bottom: RM63's own replacement wording was false, which is the third
turn of the same screw.
"""

import pytest
from just_dna_format.pgx import PharmVariantRow
from just_dna_format.spec import VariantRow

#: Real locus — the MTHFR C677T row the corpus uses — so the only thing under test is the cell.
_RSID = "rs1801133"


def _variant(genotype: str) -> VariantRow:
    return VariantRow(
        rsid=_RSID, genotype=genotype, weight=1.0, state="risk",
        conclusion="reduced MTHFR activity",
    )


@pytest.mark.parametrize(
    "genotype,why",
    [
        ("0/1", "the unphased heterozygote, and the single most likely paste"),
        ("0|1", "the phased one — the pipe is legal here, so only the members give it away"),
        ("1/1", "homozygous ALT; nothing about it is malformed as a *string*"),
        ("1/2", "two ALTs at a multi-allelic site, which has no zero to hint at an index"),
        ("./.", "VCF's no-call, which carries no digit at all"),
        ("0/1/1", "triploid — before this it got the two-allele-ceiling explanation instead"),
        ("12/1", "multi-digit indices, so the rule is not 'a single character'"),
    ],
)
def test_a_gt_field_is_named_as_allele_indices(genotype: str, why: str) -> None:
    with pytest.raises(ValueError) as excinfo:
        _variant(genotype)
    message = str(excinfo.value)
    assert "VCF GT" in message, (genotype, why, message)
    assert "indices" in message, (genotype, why, message)
    # The remedy has to be actionable, so the message says what to translate *against* — the record's
    # own REF/ALT — and that those cannot be resolved from a genotype cell, which carries neither.
    assert "REF" in message and "ALT" in message, (genotype, why, message)


def test_the_notation_is_diagnosed_before_the_arity_is_counted() -> None:
    """`0/1/1` is a notation defect, not a ploidy one, and the 0.6 ploidy fix made that worse.

    Pinned as an exclusion as well as an inclusion: a message that is *also* about the ceiling would
    let the wrong half be the one the author acts on."""
    with pytest.raises(ValueError) as excinfo:
        _variant("0/1/1")
    message = str(excinfo.value)
    assert "VCF GT" in message
    assert "ceiling" not in message, message

    # …and a genuinely polyploid call, spelled in bases, still gets the ploidy explanation. The two
    # findings must not have collapsed into one message.
    with pytest.raises(ValueError) as excinfo:
        _variant("C/T/T")
    assert "ceiling" in str(excinfo.value)
    assert "VCF GT" not in str(excinfo.value)


def test_no_verdict_moved() -> None:
    """The diagnosis may not make anything legal illegal — it only renames a refusal already there.

    The grammar's own members are the risk: a symbolic allele is bracketed and colon-separated, `*` is
    one character, and `ALLELE_PATTERN` is `^[ACGT]+$`, so no legal genotype member can be a digit run
    — but that is an argument, and this is the check."""
    for legal in ("A/G", "C|C", "A", "*", "*/A", "<DEL:1500>/A", "A|G", "<CNV:TR:30>"):
        assert _variant(legal).genotype == legal


def test_the_shared_grammar_carries_it_to_the_pgx_table_too() -> None:
    """`genotype` lives on `AuthoredModel`, so `PharmVariantRow` gets the diagnosis for free.

    Worth pinning rather than assuming: the reason the grammar moved onto the base in 0.5 was that a
    per-model copy drifts, and a diagnosis added to one arm of a shared validator is the same risk in
    miniature."""
    with pytest.raises(ValueError, match="VCF GT"):
        PharmVariantRow(rsid=_RSID, genotype="0/1", drug="warfarin", conclusion="x")
    assert PharmVariantRow(
        rsid=_RSID, genotype="C/T", drug="warfarin", conclusion="x"
    ).genotype == "C/T"


# ── R2-14: the correction that was itself an overclaim ──────────────────────────────────────────
def test_a_phased_homozygote_loads_so_a_pipe_does_not_mean_heterozygous() -> None:
    """The third turn of one screw, pinned so there is no fourth.

    The original comment on this validator claimed a pipe encodes *which homolog* an allele sits on.
    RM63 refuted that correctly — VCF defines allele order only within a phase set, and `variants.csv`
    carries no phase-set column — and replaced it with a claim about **zygosity**: "read a pipe here as
    heterozygous, phase recorded but unaddressable". Nobody checked the new half. `1|1` is an ordinary
    phased homozygous call, so the replacement was false of a genotype the model accepts.

    A correction is exactly where this happens: the reviewer checks the claim being removed, not the
    one going in. What survives is the half RM63 actually established — phase recorded, unaddressable
    — and that is what both the comment and the printed `describe` output now say.
    """
    assert _variant("C|C").genotype == "C|C"
    # …and the pipe is preserved rather than normalized to a slash, because the authored order is a
    # round-trip invariant (P7) even though no consumer can address the homologs it names.
    assert _variant("G|A").genotype == "G|A"
    # The unphased arm still demands sorting; the phased one still must not, or `G|A` would be rewritten
    # into a different authored cell.
    with pytest.raises(ValueError, match="alphabetically sorted"):
        _variant("G/A")
