"""What a compile does with a genotype naming VCF's `*` (0.6, RM59).

The grammar half is `schema/tests/test_unobservable_allele.py`. This is the other half: a `*` has to
survive resolution, materialization and the round trip, and — the part that is easy to get wrong —
it must not be read as a *contradiction* by the checks that compare a genotype against a locus.

**The real failure this pins.** `*` says nothing about which alleles a locus has, and no source ever
spells one: Ensembl, ClinVar and dbSNP all publish `ref`/`alts` in bases. So an rsid-authored `*/T`
resolved against its real `A>T` locus produced `{'*','T'} ⊄ {'A','T'}`, fell through to the
substitution arm of `hosting_verdict` — *no shared flank, so a mismatch is a real contradiction* — and
came back a confident `False`. The locus was then dropped from the expansion and the row left
unresolved, so widening the grammar alone would have made `*` authorable and uncompilable in the same
release, refusing under `strict` for a reason no authored edit could clear.

Every locus below is a real GRCh38 HBB record, taken from `reference_examples/pathogenic_clinvar/`'s
own resolution table, and the overlap is real rather than illustrative: `rs2494292050` at 11:5225640
is a 13 bp deletion (`CACTTTCTGATAGG>C`) covering 5225641–5225653, and `rs281864530` at 11:5225649
(`A>T`) sits inside it. A sample heterozygous for that deletion is precisely the sample whose call at
5225649 cannot observe the second allele, which is what a joint caller writes as `ALT=T,*`.
"""

from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import _spelling_clauses as _compiler_clauses
from just_dna_compiler.compiler import compile_module, reverse_module, validate_spec
from just_dna_compiler.resolution import _spelling_clauses as _resolution_clauses
from just_dna_compiler.resolution import hosting_verdict, undecided_reason
from just_dna_format.alleles import UNOBSERVABLE_ALLELE, non_nucleotide_reason

_SPEC_YAML = (
    "schema_version: '1.0'\n"
    "module:\n"
    "  name: rm59\n"
    "  title: RM59\n"
    "  description: the allele that could not be observed\n"
    "  report_title: RM59\n"
    "genome_build: GRCh38\n"
)

_VARIANTS_HEADER = "rsid,chrom,start,ref,alts,genotype,state,conclusion,gene\n"

#: The multi-allelic ALT cell a joint caller emits at an overlapped site. Comma-separated *inside* the
#: cell, so it is quoted — the same shape `reference_examples/pathogenic_clinvar/` uses for `"A,C,T"`.
_ALTS = f'"T,{UNOBSERVABLE_ALLELE}"'

#: The overlapped SNP, spelled the way a joint-called VCF spells it under an overlapping deletion.
_OVERLAPPED = (
    f"rs281864530,11,5225649,A,{_ALTS},{UNOBSERVABLE_ALLELE}/T,risk,"
    "the second allele here was not observable — an HBB deletion called elsewhere overlaps it,HBB\n"
)

#: The deletion doing the overlapping, authored plainly. Real ClinVar record, 13 bp.
_DELETION = (
    "rs2494292050,11,5225640,CACTTTCTGATAGG,C,C/CACTTTCTGATAGG,risk,"
    "a 13 bp HBB deletion,HBB\n"
)

_RSIDS = ("rs281864530", "rs2494292050")


#: The rsid-authored spelling of the same call — no coordinate, so resolution has to place it.
_OVERLAPPED_BY_RSID = (
    f"rs281864530,,,,,{UNOBSERVABLE_ALLELE}/T,risk,"
    "the second allele here was not observable,HBB\n"
)

#: What a resolver actually returns for that rsid. **No `*` anywhere** — Ensembl, ClinVar and dbSNP
#: publish alleles in bases, so this is the shape every real injected table has, and it is why the
#: abstention has to exist rather than relying on the ALT list to carry the marker.
_RESOLUTION = (
    "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
    "rs281864530,rs281864530,11,5225649,A,T,GRCh38,0,authored,resolved\n"
)


def _spec(directory: Path, variant_rows: str, resolution: str | None = None) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "module_spec.yaml").write_text(_SPEC_YAML)
    (directory / "variants.csv").write_text(_VARIANTS_HEADER + variant_rows)
    if resolution is not None:
        (directory / "resolution.csv").write_text(resolution)
    # Grounding is mandatory whenever `variants.csv` is present, and `pmid` must denote a real PubMed
    # record. `16199547` is a real PMID already cited by `reference_examples/hfe_hemochromatosis`; it
    # is here to satisfy that requirement, not as a claim that the paper is about these HBB records.
    #
    # Cited per variant row actually written, rather than over a fixed list: a study naming an rsid the
    # module does not carry earns its own warning, which would sit in `result.warnings` next to the
    # ones these tests assert about and make a passing run look noisier than it is.
    cited = [row.split(",", 1)[0] for row in variant_rows.splitlines() if row.strip()]
    (directory / "studies.csv").write_text(
        "rsid,pmid\n" + "".join(f"{rsid},16199547\n" for rsid in cited)
    )
    return directory


def _weights(out: Path) -> pl.DataFrame:
    return pl.read_parquet(out / "weights.parquet")


# ── the predicate: `*` abstains, and the observable half is still judged ─────────────────────────


def test_a_star_does_not_make_a_locus_unable_to_host_the_call() -> None:
    """The regression the whole lane turns on — `False` here drops the locus and unresolves the row.

    Both spellings must agree: the locus as a source publishes it (`A>T`, no `*` anywhere) and the
    locus as a joint caller writes it (`T,*`). A verdict that depended on whether the ALT list happened
    to carry the marker would make resolution's answer depend on which file the coordinates came from.
    """
    assert hosting_verdict(f"{UNOBSERVABLE_ALLELE}/T", "A", "T") is True
    assert hosting_verdict(f"{UNOBSERVABLE_ALLELE}/T", "A", f"T,{UNOBSERVABLE_ALLELE}") is True
    assert hosting_verdict(f"{UNOBSERVABLE_ALLELE}/A", "A", "T") is True


def test_the_observable_half_is_still_a_real_contradiction() -> None:
    """Abstention drops the member, never the verdict — otherwise `*` would launder a wrong genotype.

    `G` is not an allele of this locus, and the locus is a substitution, so there is no spelling freedom
    to hide behind. Pinned beside the case above because the tempting implementation — withhold the
    whole verdict whenever a `*` appears — passes that test and silently loses this one.
    """
    assert hosting_verdict(f"{UNOBSERVABLE_ALLELE}/G", "A", "T") is False
    assert hosting_verdict("G/G", "A", "T") is False


def test_a_call_that_observed_nothing_is_undecided_never_false() -> None:
    """`*/*` is the house algebra: nothing was seen, so nothing about the locus can be decided."""
    assert hosting_verdict(
        f"{UNOBSERVABLE_ALLELE}/{UNOBSERVABLE_ALLELE}", "A", "T"
    ) is None


def test_abstention_only_ever_adds_acceptances() -> None:
    """A genotype with no `*` must compare exactly as it did — the stability property, checked.

    Every ordinary pair through the real predicate: the substitution contradiction stays `False`, the
    match stays `True`, and the indel reconciliation RM31 shipped is untouched.
    """
    unchanged = {
        ("A/T", "A", "T"): True,
        ("C/G", "A", "T"): False,
        ("C/CAG", "AGAG", "AG"): True,   # RM31's SHOX deletion, two spellings of one event
    }
    assert {k: hosting_verdict(*k) for k in unchanged} == unchanged


# ── the module: it validates, compiles, and survives the round trip ──────────────────────────────


@pytest.mark.parametrize("strict", [False, True])
def test_a_starred_module_validates_and_compiles_in_both_modes(tmp_path: Path, strict: bool) -> None:
    """Both surfaces, because `validate` is the author's pre-flight and must refuse what compile does.

    Fails on the pre-RM59 code at the load step: `variants.csv` could not even be read, because the
    genotype grammar rejected the cell.
    """
    spec = _spec(tmp_path / "spec", _OVERLAPPED + _DELETION)

    report = validate_spec(spec, strict=strict)
    assert report.valid, report.errors

    result = compile_module(spec, tmp_path / "out", strict=strict)
    assert result.success, result.errors

    # The row reached the artifact rather than being dropped or silently reference-ified. `genotype`
    # materializes as the split allele list, so the `*` has to survive as a *member* — the shape a
    # consumer joins against, and the one a filter on "looks like a base" would quietly discard.
    weights = _weights(tmp_path / "out")
    assert set(weights["rsid"].to_list()) == set(_RSIDS)
    starred = weights.filter(pl.col("rsid") == "rs281864530")
    assert starred["genotype"].to_list() == [f"{UNOBSERVABLE_ALLELE}/T".split("/")]


@pytest.mark.parametrize(
    "call",
    [
        f"{UNOBSERVABLE_ALLELE}/T",   # unphased, and therefore sorted
        f"T|{UNOBSERVABLE_ALLELE}",   # phased: order is significant and deliberately NOT sorted
    ],
)
def test_the_round_trip_is_a_fixed_point(tmp_path: Path, call: str) -> None:
    """P7 over a `*`-carrying genotype: compile → reverse → compile preserves every identity field.

    The genotype is read back off the *rebuilt* CSV as well as off the parquet, because the reverse
    writer is the touch point a new spelling is most likely to be lost at.

    The phased case is here because phase is the one arm where order carries meaning, so a rejoin that
    sorted or normalized on the way out would be invisible in the unphased case and lossy in this one —
    `T|*` must come back `T|*`, not `*|T`.
    """
    spec = _spec(tmp_path / "spec", _OVERLAPPED.replace(f"{UNOBSERVABLE_ALLELE}/T", call) + _DELETION)
    first = compile_module(spec, tmp_path / "out", strict=True)
    assert first.success, first.errors

    rebuilt = tmp_path / "rebuilt"
    reverse_module(tmp_path / "out", rebuilt)
    assert call in (rebuilt / "variants.csv").read_text()

    second = compile_module(rebuilt, tmp_path / "out2", strict=True)
    assert second.success, second.errors

    for out in (tmp_path / "out", tmp_path / "out2"):
        assert (out / "manifest.json").exists()
    assert _weights(tmp_path / "out2")["genotype"].to_list() == \
        _weights(tmp_path / "out")["genotype"].to_list()
    assert first.manifest.content_signature == second.manifest.content_signature


def test_an_rsid_authored_star_resolves_against_a_locus_that_spells_no_star(tmp_path: Path) -> None:
    """The whole-path version of the regression, and the case a real module is in.

    No source publishes `*` in an ALT list, so an injected `resolution.csv` never carries one: the
    locus is `A>T` and the call is `*/T`. Before the abstention this pair was a positive contradiction,
    so the locus was dropped, the row went unresolved, and a `strict` compile refused — the module
    below is the one an author would actually have, and it would not have compiled.

    Asserted on the artifact rather than on the predicate: the coordinates have to arrive on the row,
    which is what proves the locus was kept rather than merely not-refused.

    Demonstrated on the broken behaviour rather than assumed — with the abstention removed this module
    does not compile at all, and the message is a false accusation: *"allele(s) `*` are not among the
    resolved alleles at this locus (A/T) — either the genotype is wrong or the resolving source's
    allele list is incomplete"*. Neither is true; `*` is not an allele the source was ever going to
    list.
    """
    spec = _spec(tmp_path / "spec", _OVERLAPPED_BY_RSID, resolution=_RESOLUTION)

    result = compile_module(spec, tmp_path / "out", strict=True)
    assert result.success, result.errors

    weights = _weights(tmp_path / "out")
    placed = weights.filter(pl.col("rsid") == "rs281864530")
    assert placed["start"].to_list() == [5225649]
    assert placed["genotype"].to_list() == [[UNOBSERVABLE_ALLELE, "T"]]

    # And nothing told the author their genotype contradicts their locus.
    assert [w for w in result.warnings if "not alleles of" in w or "cannot host" in w] == []


def test_no_symbolic_allele_finding_claims_the_star(tmp_path: Path) -> None:
    """RM5's check must say nothing about `*` — it is not angle-bracketed and not its business.

    The separation is the item, so it is asserted on the *compiler's own output* rather than on the
    predicate alone: a warning telling this author about `<DEL:1500>` and the closed five would be
    pointing them at a grammar that has nothing to do with what they wrote.
    """
    spec = _spec(tmp_path / "spec", _OVERLAPPED + _DELETION)
    result = compile_module(spec, tmp_path / "out", strict=True)

    assert result.success, result.errors
    noise = [w for w in result.warnings if "symbolic" in w.lower() or "<DEL" in w]
    assert noise == []


def test_a_star_in_the_alt_list_does_not_break_indel_reconciliation() -> None:
    """`*` must be ignored on the **locus** side too, and leaving it in was a confident wrong answer.

    `parsimony_reduce` strips the flank a collection shares, and `*` has none — so a `*` sitting in the
    ALT list stops the whole set reducing, RM31's two spellings of one deletion stop matching, and the
    verdict comes back `False` rather than `True`. That is a correctly transcribed indel refused under
    `--strict`, with a message advising the author to "replace it with the alleles the locus actually
    has". `ALT=AG,*` is ordinary joint-caller output, so this is the common case, not a corner.
    """
    # RM31's SHOX deletion: ClinVar's `C/CAG` against Ensembl's `AGAG>AG` spelling of one 2 bp event.
    assert hosting_verdict("C/CAG", "AGAG", "AG") is True
    assert hosting_verdict("C/CAG", "AGAG", f"AG,{UNOBSERVABLE_ALLELE}") is True

    # And a locus with nothing observable left decides nothing, rather than contradicting everything.
    assert hosting_verdict("A/T", UNOBSERVABLE_ALLELE, UNOBSERVABLE_ALLELE) is None


def test_every_undecided_cause_gets_its_own_reason() -> None:
    """`None` has four causes; the warning used to assert one of them for all four.

    Each case below really returns `None` from the predicate — asserted, so the table cannot drift into
    describing shapes that are actually decided — and each must draw its own explanation. The all-`*`
    row is the one that made this worth fixing: the old sentence told the reader to check the pair
    against a reference sequence, and no reference can say what a call did not observe.
    """
    cases = {
        ("*/*", "A", "T"): "observed no allele",                    # RM59
        ("<DEL:1500>/A", "A", "AT"): "deliberately unspelled",      # RM5
        ("C/C", "AGAG", "AG"): "carries no flank",                  # homozygous, no frame
        # A 2 bp insertion of `CT` against the locus's 2 bp `AG` deletion: same event size, different
        # bases, which is the one case only a reference sequence can settle — the original cause.
        ("C/CCT", "AGAG", "AG"): "same size but different content",
    }
    for args, expected in cases.items():
        assert hosting_verdict(*args) is None, args
        assert expected in undecided_reason(*args), (args, undecided_reason(*args))

    # The four are genuinely distinct sentences, not one sentence with four spellings.
    assert len({undecided_reason(*args) for args in cases}) == len(cases)


def test_both_spelling_builders_have_an_arm_for_every_reason() -> None:
    """There are **two** clause builders, and a missing arm in either is silent rather than loud.

    `compiler._spelling_clauses` and `resolution._spelling_clauses` are deliberately separate code
    reading differently around their own call sites, sharing only the classification. Neither raises on
    an unknown reason — it filters by reason, so the allele is simply dropped from the explanation, and
    a locus whose only odd allele is unclassified produces a sentence with nothing in it. RM59 added
    the fourth reason; this is what stops a fifth from reaching one builder and not the other.

    Discovered by *behaviour* — every reason `non_nucleotide_reason` actually returns for a real value —
    rather than from a hand-kept list, which is the half of such a guard that rots.
    """
    probes = ["R", "<DEL:1500>", UNOBSERVABLE_ALLELE, "DELTCT", "AAAGGGGCG(2)", "<FOO>"]
    reasons = {r for r in (non_nucleotide_reason(a) for a in probes) if r is not None}
    assert len(reasons) >= 4, reasons

    for builder in (_compiler_clauses, _resolution_clauses):
        for allele, reason in ((a, non_nucleotide_reason(a)) for a in probes):
            if reason is None:
                continue
            rendered = builder({allele: reason})
            assert rendered, f"{builder.__module__}: no clause for reason {reason!r} ({allele!r})"
            assert repr(allele) in rendered


def test_a_star_in_the_alt_list_is_not_reported_as_a_grammar_gap(tmp_path: Path) -> None:
    """The message repair that came with the reason class.

    A genotype the locus really cannot host produces the "genotype is not the problem" caveat, which
    enumerates the locus's own odd alleles. `*` used to be filed there as a *grammar gap a future
    release may widen* — false, permanently: there is no sequence for a grammar to hold. It is now
    named for what it is, and the two readings are not allowed to share a sentence.
    """
    wrong_call = (
        f"rs281864530,11,5225649,A,{_ALTS},C/G,risk,"
        "a genotype naming an allele this locus does not have,HBB\n"
    )
    spec = _spec(tmp_path / "spec", wrong_call)
    report = validate_spec(spec, strict=False)

    caveats = [w for w in report.warnings if "genotype is not the problem" in w]
    assert caveats, report.warnings
    # Keyed on the *notation* clause's own distinctive wording rather than on a phrase both clauses
    # could contain — the two readings must not be merged, and asserting on a shared substring would
    # not notice if they were.
    assert all("repeat notation" not in c for c in caveats)
    assert any("overlapping-deletion" in c for c in caveats)
