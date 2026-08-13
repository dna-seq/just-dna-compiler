"""The allele that could not be observed — VCF's `*` in a genotype (0.6, RM59).

`*` is what any modern joint-called VCF puts in ALT at a site some deletion called elsewhere overlaps,
so `ALT=A,*` with `GT=0/2` is ordinary consumer data. Until RM59 `alts='*'` loaded (that column has no
grammar) while `genotype='*/A'` was rejected, so **no row could be written for such a call at all** —
and a consumer that drops the `*` reads the call as reference-like and takes the reference conclusion.
That is the no-call-is-not-hom-reference error `requires_callable` exists to prevent, arriving through
a spelling rather than through a missing record.

**The point of the item is that `*` is not RM5's axis**, so half of what is pinned here is a
*separation*: a symbolic allele names a variant whose sequence the grammar cannot spell, and `*` names
no variant at all — it makes an observability claim, which is the callability axis. The two share a
column and must never share machinery, so the tests below assert what `*` is *not* claimed by as
firmly as what it is.

Every locus is a real GRCh38 HBB record taken from `reference_examples/pathogenic_clinvar/`'s own
resolution table, and the overlap is a real one: `rs2494292050` at 11:5225640 is a 13 bp deletion
(`CACTTTCTGATAGG>C`) spanning 5225641–5225653, which covers `rs281864530` at 11:5225649 (`A>T`). A
sample carrying that deletion on one homolog is exactly the sample whose call at 5225649 cannot
observe the other allele.
"""

import pytest
from just_dna_format.alleles import (
    MISSING_ALLELE,
    SYMBOLIC_ALLELE_TYPES,
    UNOBSERVABLE_ALLELE,
    is_symbolic_allele,
    is_unobservable_allele,
    non_nucleotide_reason,
    parse_symbolic_allele,
    symbolic_allele_defect,
)
from just_dna_format.base import derive_variant_key, genotype_allele_ok
from just_dna_format.pgx import HaplotypeRow
from just_dna_format.spec import VariantRow
from just_dna_format.vocab import validate_allele
from just_dna_format.vrs import derive_vrs_allele_id

#: The overlapped SNP: real, GRCh38, and inside the span of a real deletion at the same gene.
_CHROM, _START, _REF, _ALT = "11", 5225649, "A", "T"


def _variant(genotype: str, **extra: object) -> VariantRow:
    """A real overlapped HBB site, spelled the way a joint-called VCF spells it."""
    return VariantRow(
        chrom=_CHROM, start=_START, ref=_REF, alts=f"{_ALT},{UNOBSERVABLE_ALLELE}",
        genotype=genotype, state="risk", gene="HBB",
        conclusion="the second allele at this position was not observable",
        **extra,
    )


# ── the grammar admits it, in all three arms ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "genotype",
    [
        f"{UNOBSERVABLE_ALLELE}/{_ALT}",      # unphased pair — the GT=0/2 case, canonically sorted
        f"{UNOBSERVABLE_ALLELE}|{_ALT}",      # phased pair
        UNOBSERVABLE_ALLELE,                  # hemizygous single — the one allele was not observable
        f"{UNOBSERVABLE_ALLELE}/{UNOBSERVABLE_ALLELE}",  # neither allele could be observed
    ],
)
def test_the_genotype_grammar_admits_the_unobservable_allele(genotype: str) -> None:
    """All three arms of `_validate_genotype`, because the grammar is written out three times.

    Fails on the pre-RM59 code by construction: every one of these raised
    "genotype alleles must be nucleotides, or a symbolic/structural allele…".
    """
    assert _variant(genotype).genotype == genotype


def test_the_helper_and_the_model_agree_about_every_member() -> None:
    """`genotype_allele_ok` is the one place the decision lives, so it must not drift from the model.

    Checked as set equality over a mixed bag rather than member by member: a widening that leaked into
    `N` or `.` would pass a per-member assertion on `*` and be caught here.
    """
    accepted = {a for a in (UNOBSERVABLE_ALLELE, "A", "AC", "<DEL:1500>", "<*>", "N", ".", "")
                if genotype_allele_ok(a)}
    assert accepted == {UNOBSERVABLE_ALLELE, "A", "AC", "<DEL:1500>"}


def test_the_canonical_spelling_is_the_sorted_one_and_the_message_names_it() -> None:
    """`*` sorts before the bases, so the VCF-order transcription earns the existing sorting message.

    Not a special case and deliberately not made one: the unphased arm has always required the pair to
    be sorted so one genotype has one spelling, and `<DEL:1500>/A` obeys the same rule. What matters is
    that the refusal is *mechanical* — it names the exact string to write — rather than a dead end.
    """
    canonical = "/".join(sorted([_ALT, UNOBSERVABLE_ALLELE]))
    assert canonical == f"{UNOBSERVABLE_ALLELE}/{_ALT}"
    assert _variant(canonical).genotype == canonical

    with pytest.raises(ValueError, match="alphabetically sorted") as caught:
        _variant(f"{_ALT}/{UNOBSERVABLE_ALLELE}")
    assert repr(canonical) in str(caught.value)


# ── the separation from RM5, which is the item ──────────────────────────────────────────────────


def test_the_unobservable_allele_is_not_a_symbolic_allele() -> None:
    """None of RM5's machinery may claim `*` — it names no variant, so it has no type and no length.

    `<*>` is the near neighbour that makes the distinction concrete: it is angle-bracketed, so it *is*
    symbolic-shaped and gets RM5's `unknown_type` diagnosis, while `*` is a different token on a
    different axis and is none of RM5's business.
    """
    assert not is_symbolic_allele(UNOBSERVABLE_ALLELE)
    assert parse_symbolic_allele(UNOBSERVABLE_ALLELE) is None
    assert symbolic_allele_defect(UNOBSERVABLE_ALLELE) is None
    assert UNOBSERVABLE_ALLELE not in SYMBOLIC_ALLELE_TYPES

    assert is_symbolic_allele("<*>")
    assert symbolic_allele_defect("<*>") == "unknown_type"


def test_is_unobservable_allele_claims_only_the_one_token() -> None:
    """Exact, unlike `is_symbolic_allele`'s deliberate leniency — there is no near miss to be kind to.

    **`*1` is the near neighbour that is actually in the corpus**, and it is the reason the exactness is
    load-bearing rather than tidy: `reference_examples/cyp2c19_star_alleles` is full of star-allele
    *names* (`*1`, `*2`) in `haplotype_name` and `AlleleFunctionRow.allele`, where the character means
    "PGx haplotype", a third role again — neither a sequence nor an observability claim. A prefix or
    substring test here would claim every one of them.
    """
    probes = (
        UNOBSERVABLE_ALLELE, f" {UNOBSERVABLE_ALLELE} ",   # the marker, bare and padded
        "*1", "*2", "*17",                                  # PGx star-allele names, really in the corpus
        "<*>", "**", "A*", "A", "",
    )
    claimed = {a for a in probes if is_unobservable_allele(a)}
    assert claimed == {UNOBSERVABLE_ALLELE, f" {UNOBSERVABLE_ALLELE} "}

    # And the genotype grammar does not admit a star-allele name either: a diplotype is `DiplotypeRow`'s
    # business, not a `variants.csv` genotype's.
    assert not genotype_allele_ok("*1")


def test_the_missing_marker_and_the_unobservable_marker_stay_distinct() -> None:
    """`.` and `*` are the two answers that name no allele, and neither may absorb the other.

    They landed one lane apart (RM58 and RM59) and merging them is the obvious tidy-up, because both are
    punctuation standing where a sequence goes and neither will ever become spellable. The claims are
    opposite: `.` says **no alternate allele exists** — about the variant — and `*` says an allele
    **could not be observed** — about the sample's call. So the consequences differ in kind, which is
    what this pins:

    * `.` is an identity defect with a clean authored repair, and `derive_variant_key` really does fold
      it in, so the two spellings of one monomorphic site key differently.
    * `*` is not a defect at all. The cell is correct and nothing needs editing.

    Merging them would either accuse a correct `*` row or silence a real `.` collision.
    """
    assert non_nucleotide_reason(MISSING_ALLELE) == "missing"
    assert non_nucleotide_reason(UNOBSERVABLE_ALLELE) == "unobservable"
    assert MISSING_ALLELE != UNOBSERVABLE_ALLELE

    # Only `*` is admitted to a genotype: `.` names no allele for a call to carry.
    assert genotype_allele_ok(UNOBSERVABLE_ALLELE)
    assert not genotype_allele_ok(MISSING_ALLELE)

    # And the identity consequence is `.`'s alone — RM58's, and still live.
    dotted = derive_variant_key(None, _CHROM, _START, _REF, MISSING_ALLELE)
    empty = derive_variant_key(None, _CHROM, _START, _REF, None)
    assert dotted != empty


def test_non_nucleotide_reason_separates_all_five_kinds() -> None:
    """Five reasons with five different consequences, and `*` used to be filed under the wrong one.

    Before RM59 it answered `"notation"`, whose documented reading is *a grammar gap a future release
    may widen* — permanently false here, because there is no sequence for any grammar to hold. Asserted
    as one mapping so a future arm cannot quietly absorb a neighbour.
    """
    probes = {UNOBSERVABLE_ALLELE: "unobservable", MISSING_ALLELE: "missing",
              "<DEL:1500>": "symbolic", "DELTCT": "notation", "R": "ambiguity", _REF: None}
    assert {a: non_nucleotide_reason(a) for a in probes} == probes


# ── the columns that still refuse it, and why that is the same decision ─────────────────────────


def test_an_allele_column_still_refuses_it() -> None:
    """RM59 widened `genotype` and nothing else, deliberately.

    `HaplotypeRow.allele` and `VariantRow.effect_allele` name the allele a *rule* is about, and a rule
    about an allele nobody observed states nothing — while a genotype is the one column that records an
    observation, which is why it is the one column `*` belongs in.
    """
    with pytest.raises(ValueError, match="must be nucleotides"):
        validate_allele(UNOBSERVABLE_ALLELE)
    with pytest.raises(ValueError, match="must be nucleotides"):
        HaplotypeRow(haplotype_name="*1", allele=UNOBSERVABLE_ALLELE, rsid="rs281864530")
    with pytest.raises(ValueError, match="must be nucleotides"):
        _variant(f"{UNOBSERVABLE_ALLELE}/{_ALT}", effect_allele=UNOBSERVABLE_ALLELE)


# ── identity: `*` names no variant, so it mints no content-addressed id ─────────────────────────


def test_it_mints_no_content_addressed_identity() -> None:
    """A VRS allele id is a digest of a real allele at a real place; `*` is neither.

    The contrast is the assertion: the *same* real locus mints a `ga4gh:VA.…` id for its actual ALT and
    falls back to the coordinate key once `*` is the allele on offer. A `*` that minted an id would be
    a content-addressed name for the absence of an observation.
    """
    assert derive_vrs_allele_id(_CHROM, _START, _REF, _ALT).startswith("ga4gh:VA.")
    assert derive_vrs_allele_id(_CHROM, _START, _REF, UNOBSERVABLE_ALLELE) is None

    starred = derive_variant_key(None, _CHROM, _START, _REF, UNOBSERVABLE_ALLELE)
    assert starred == f"{_CHROM}:{_START}:{_REF}:{UNOBSERVABLE_ALLELE}"
    assert not starred.startswith("ga4gh:")

    # The multi-allelic spelling a real record carries is a coordinate key too — one id per one allele
    # is the rule, and a comma-joined cell names more than one.
    both = derive_variant_key(None, _CHROM, _START, _REF, f"{_ALT},{UNOBSERVABLE_ALLELE}")
    assert not both.startswith("ga4gh:")


def test_a_starred_genotype_does_not_change_the_rows_identity() -> None:
    """The genotype is not part of `variant_key`, so widening it moves no identity.

    Worth pinning rather than assuming: the whole lane is a widening, and a genotype that reached the
    key would make every `*` row a new variant.
    """
    observed = _variant(f"{UNOBSERVABLE_ALLELE}/{_ALT}")
    ordinary = _variant(f"{_ALT}/{_ALT}")
    assert observed.variant_key == ordinary.variant_key
