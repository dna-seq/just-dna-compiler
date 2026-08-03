"""`hosting_verdict` — can a locus host a genotype? Three answers, on real published spellings (RM31).

The predicate is shared three ways (this module's resolver, the enricher's deprecated DuckDB path, and
`enrich()`'s forward resolution), and digest parity between the first two is a documented guarantee, so
its behaviour is pinned here rather than in any one caller. The monotonicity test at the bottom is the
one that protects every already-compiled module: normalization may only ever *add* acceptances.
"""

from pathlib import Path

import csv
import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_compiler.resolution import genotype_fits, hosting_verdict

_EXAMPLES = Path(__file__).resolve().parents[2] / "reference_examples"


# ── the three answers ───────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "label,genotype,ref,alts,expected",
    [
        # The case that produced the item: ClinVar drafts `X:634689 CAG>C`, so the human writes the
        # genotype in that frame; Ensembl publishes the same 2 bp AG deletion as `X:634690 AGAG>AG`.
        ("SHOX deletion, two published spellings", "C/CAG", "AGAG", "AG", True),
        ("...and the other way round", "AG/AGAG", "CAG", "C", True),
        # Unchanged behaviour: the raw strings already matched.
        ("plain substitution", "C/T", "C", "T", True),
        ("het at a multi-allelic site", "A/T", "C", "A,T", True),
        ("nothing recorded about the locus", "A/G", None, None, True),
        ("ref recorded, no alts", "A/G", "A", None, True),
        # A real contradiction, and it must stay one: no flank means no freedom to re-anchor, so a
        # strand-flipped SNV genotype is still a hard finding rather than an undecidable.
        ("strand-flipped SNV genotype", "A/G", "C", "T", False),
        ("MNV with a different base", "AT/GC", "AT", "GG", False),
        # `rs281864532` files a 1 bp insertion and a 2 bp deletion under one rsID at one position.
        # Re-anchoring cannot change how many bases an event adds or removes, so this is decidable.
        ("1 bp insertion genotype at a 2 bp deletion locus", "G/GT", "GTT", "G", False),
        ("2 bp deletion genotype at a 1 bp insertion locus", "GTT/G", "G", "GT", False),
        # The same SHOX deletion written one base further right (the reference reads `C A G A G` from
        # 634689, so `GAG>G` at 634691 is that AG deletion again) reduces to the event `GA` where the
        # genotype's reduces to `AG`: same size, different content. Either one indel re-anchored inside
        # the repeat or two different variants, and only the reference sequence can say which.
        ("same-size events, rotated content", "C/CAG", "GAG", "G", None),
        # A homozygous indel genotype carries no frame: one string has nothing to be relative to.
        ("homozygous indel genotype", "C/C", "AGAG", "AG", None),
        ("single-allele (hemizygous) indel genotype", "C", "AGAG", "AG", None),
        # …but at a substitution locus a single allele is still decidable, because there is no
        # spelling freedom to appeal to.
        ("homozygous genotype at a substitution locus", "G/G", "C", "T", False),
    ],
)
def test_the_verdict_matrix(label, genotype, ref, alts, expected) -> None:
    assert hosting_verdict(genotype, ref, alts) is expected, label


def test_genotype_fits_keeps_what_it_cannot_decide() -> None:
    """The boolean face collapses `None` into "keep", which is the module's standing doctrine: only a
    positive contradiction rejects, exactly as a locus with no recorded alleles is kept."""
    assert genotype_fits("C/C", "AGAG", "AG") is True        # undecided → kept
    assert genotype_fits("G/GT", "GTT", "G") is False        # decided against → dropped
    assert genotype_fits("C/CAG", "AGAG", "AG") is True      # reconciled


# ── the property that protects every already-compiled module ────────────────────────────────────


def _real_pairs() -> list[tuple[str, str, str, str]]:
    """Every (genotype, ref, alts) the reference examples actually contain, from their own files.

    Built from `variants.csv` + `resolution.csv` rather than invented: the claim under test is about
    real data, and a synthetic corpus would prove nothing about the modules that exist.
    """
    pairs: list[tuple[str, str, str, str]] = []
    for spec in sorted(_EXAMPLES.iterdir()):
        variants_path, resolution_path = spec / "variants.csv", spec / "resolution.csv"
        if not (variants_path.is_file() and resolution_path.is_file()):
            continue
        genotypes: dict[str, str] = {}
        with variants_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                key = (row.get("rsid") or "").strip()
                if key and (row.get("genotype") or "").strip():
                    genotypes[key] = row["genotype"].strip()
        with resolution_path.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                genotype = genotypes.get((row.get("variant_key") or "").strip())
                if genotype and (row.get("ref") or "").strip() and (row.get("alts") or "").strip():
                    pairs.append((spec.name, genotype, row["ref"].strip(), row["alts"].strip()))
    return pairs


def test_the_corpus_is_not_empty() -> None:
    """A property test over nothing passes vacuously — so check the corpus exists first."""
    pairs = _real_pairs()
    assert len(pairs) > 20, pairs
    assert len({spec for spec, *_ in pairs}) >= 2


def test_normalization_only_ever_adds_acceptances() -> None:
    """**Monotonicity, and it is what keeps every compiled digest stable.**

    A raw string match short-circuits before any reduction runs, so a locus that was hostable before is
    hostable now — byte for byte, with the same expansion and the same parquet rows. Verified against
    every real (genotype, ref, alts) triple in the reference examples: wherever the old exact-membership
    test said yes, the verdict is `True` (never `None`, never `False`).
    """
    for spec, genotype, ref, alts in _real_pairs():
        available = {ref.upper()} | {a.strip().upper() for a in alts.split(",") if a.strip()}
        raw_match = {a.upper() for a in genotype.replace("|", "/").split("/") if a} <= available
        if raw_match:
            assert hosting_verdict(genotype, ref, alts) is True, (spec, genotype, ref, alts)


def test_resolution_and_allele_membership_reach_the_same_verdict(tmp_path: Path) -> None:
    """**The two string comparisons in the compiler must not disagree.**

    `resolve_from_table` decides which loci an rsid expands onto; `_check_allele_membership` decides
    whether the genotype's alleles are among the resolved ones. Both are the same question, and while
    membership did its own exact-set difference the two halves split the moment one indel was spelled two
    ways: resolution reconciled ClinVar's `C/CAG` with Ensembl's `AGAG>AG` and expanded onto the locus,
    and then `strict` refused because the literal strings were not in the resolved set — a module the
    resolver had just accepted. Membership now asks the shared predicate.
    """
    spec = tmp_path / "indel"
    spec.mkdir()
    (spec / "module_spec.yaml").write_text(
        "schema_version: '1.0'\nmodule:\n  name: d\n  title: D\n  description: d\n  report_title: D\n"
    )
    (spec / "variants.csv").write_text(
        "rsid,genotype,state,conclusion,gene\nrs1569493663,C/CAG,risk,SHOX deletion,SHOX\n"
    )
    (spec / "studies.csv").write_text("rsid,pmid\nrs1569493663,29165669\n")
    (spec / "resolution.csv").write_text(
        "variant_key,rsid,chrom,start,ref,alts,genome_build,locus_index,source,status\n"
        "rs1569493663,rs1569493663,X,634690,AGAG,AG,GRCh38,0,manual,resolved\n"
    )
    for strict in (False, True):
        result = compile_module(spec, tmp_path / f"out_{strict}", strict=strict)
        assert result.success, (strict, result.errors)
        assert not any("not among the" in w for w in result.manifest.compilation.warnings)


def test_no_real_example_row_became_undecidable() -> None:
    """The corpus is all substitutions and clean indels, so nothing should land in the third state.

    Not a claim that `None` is rare in general — it is the honest answer for a rotation inside a repeat.
    This pins that the *existing* modules are unaffected, so a future change that starts reporting
    "could not be decided" on them shows up here rather than in a compile log.
    """
    undecided = [
        (spec, genotype, ref, alts)
        for spec, genotype, ref, alts in _real_pairs()
        if hosting_verdict(genotype, ref, alts) is None
    ]
    assert undecided == []
