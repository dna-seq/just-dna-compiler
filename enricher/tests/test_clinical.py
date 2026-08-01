"""The ClinVar `clin_sig` cross-check — allele-exactness, conflict classification, and non-escalation.

Everything here runs against the committed real ClinVar slice
(``assets/clinvar_GRCh38_slice.vcf.gz``), built into a snapshot at test time. That slice happens to
contain the exact hazard this check has to survive: **`rs334` at 11:5227002 carries `T>A` as
`pathogenic` (2 stars) and `T>G` as `likely_benign` (1 star)** — one rsID, one locus, two opposite
clinical calls. A cross-check keyed on rsID would report a module that is simply right, so the
allele-exactness is not a refinement, it is the difference between a useful check and a noisy one.
"""

from pathlib import Path

import pytest
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

from just_dna_enricher.clinical import verify_clin_sig
from just_dna_enricher.clinvar_build import build_snapshot
from just_dna_enricher.enrich import enrich

FIXTURE = Path(__file__).parents[2] / "assets" / "clinvar_GRCh38_slice.vcf.gz"

_YAML = (
    "schema_version: '1.0'\n"
    "module:\n  name: demo\n  title: Demo\n  description: d\n  report_title: Demo\n"
)

# The HBB locus both of the slice's opposed rs334 records sit at.
_CHROM, _START, _REF = "11", 5227002, "T"


@pytest.fixture(scope="module")
def snapshot(tmp_path_factory) -> Path:
    """The real slice, built once — the check reads it exactly as `enrich()` would."""
    out = tmp_path_factory.mktemp("cv")
    build_snapshot(FIXTURE, out / "cv")
    return out / "cv"


def _variant(clin_sig: str, genotype: str, alts: str = "A,G", **kw) -> VariantRow:
    return VariantRow(
        chrom=_CHROM, start=_START, ref=_REF, alts=alts, genotype=genotype,
        state="risk", conclusion="c", clin_sig=clin_sig, **kw
    )


def _resolution(variant: VariantRow, alts: str = "A,G") -> list[ResolutionRow]:
    return [
        ResolutionRow(
            variant_key=variant.variant_key, rsid="rs334", chrom=_CHROM, start=_START,
            ref=_REF, alts=alts, source="clinvar", status="resolved",
        )
    ]


# ── the core claim: the module's call is compared against ITS OWN allele ─────────────────────────


def test_an_opposed_call_on_the_pathogenic_allele_is_reported(snapshot: Path) -> None:
    """Authoring `benign` for `T>A`, which ClinVar calls pathogenic with two stars."""
    variant = _variant("benign", "A/T")
    conflicts = verify_clin_sig([variant], _resolution(variant), reference=snapshot)

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert (conflict.authored, conflict.clinvar) == ("benign", "pathogenic")
    assert conflict.alt == "A"
    assert conflict.opposed is True
    assert conflict.review_stars == 2
    assert conflict.confidence == "2-star"
    assert "reported, never overwritten" in str(conflict)


def test_the_same_call_on_the_benign_allele_is_not_reported(snapshot: Path) -> None:
    """The trap, and the reason matching is allele-exact rather than rsID-level.

    `T>G` at this locus is `likely_benign` in ClinVar, so a module calling it benign AGREES — even
    though the *same rsID* also tags a pathogenic allele two rows away. Keying on `rs334` would
    manufacture a conflict here out of ClinVar agreeing with itself.
    """
    variant = _variant("benign", "G/T")
    assert verify_clin_sig([variant], _resolution(variant), reference=snapshot) == []


def test_likely_pathogenic_does_not_conflict_with_pathogenic(snapshot: Path) -> None:
    """A difference of confidence inside one conclusion is not a disagreement worth a warning."""
    variant = _variant("likely_pathogenic", "A/T")
    assert verify_clin_sig([variant], _resolution(variant), reference=snapshot) == []


def test_clinvar_having_no_opinion_is_not_a_conflict(snapshot: Path) -> None:
    """`uncertain_significance` is not an opposing claim — there is nothing to disagree with.

    Uses the slice's real 1:66926 `AG>A`, which ClinVar classifies as uncertain.
    """
    variant = VariantRow(
        chrom="1", start=66926, ref="AG", alts="A", genotype="A/AG",
        state="risk", conclusion="c", clin_sig="pathogenic",
    )
    rows = [ResolutionRow(variant_key=variant.variant_key, chrom="1", start=66926, ref="AG",
                          alts="A", source="clinvar", status="resolved")]
    assert verify_clin_sig([variant], rows, reference=snapshot) == []


def test_a_module_making_no_clinical_claim_is_not_compared(snapshot: Path) -> None:
    variant = VariantRow(
        chrom=_CHROM, start=_START, ref=_REF, alts="A", genotype="A/T",
        state="risk", conclusion="c",
    )
    assert verify_clin_sig([variant], _resolution(variant, alts="A"), reference=snapshot) == []


def test_effect_allele_overrides_the_genotype_derivation(snapshot: Path) -> None:
    """When the author states which allele the annotation is about, that is the one compared."""
    # Genotype names both alts, so the derivation alone could not choose; effect_allele decides.
    variant = _variant("benign", "A/G", effect_allele="A")
    conflicts = verify_clin_sig([variant], _resolution(variant), reference=snapshot)
    assert [c.alt for c in conflicts] == ["A"]
    assert conflicts[0].clinvar == "pathogenic"


def test_an_ambiguous_genotype_falls_back_to_the_whole_locus(snapshot: Path) -> None:
    """With no effect_allele and a genotype naming two alts, the check compares against the locus and
    reports only when NO record there supports the authored call — conservative, never a guess.

    `benign` is supported at this locus (by `T>G`), so the fallback stays silent even though the
    pathogenic record is also present.
    """
    variant = _variant("benign", "A/G")
    assert verify_clin_sig([variant], _resolution(variant), reference=snapshot) == []


def test_the_locus_fallback_still_reports_a_wholly_unsupported_call(snapshot: Path) -> None:
    """The other half of the fallback: silence requires *some* record to agree, not merely to exist.

    The slice's 1:943234 `A>G` is `likely_benign` and nothing there is pathogenic, so a module calling
    the locus pathogenic is reported even though the ALT could not be pinned down.
    """
    variant = VariantRow(
        chrom="1", start=943234, ref="A", alts="G,C", genotype="C/G",
        state="risk", conclusion="c", clin_sig="pathogenic",
    )
    rows = [ResolutionRow(variant_key=variant.variant_key, chrom="1", start=943234, ref="A",
                          alts="G,C", source="clinvar", status="resolved")]
    conflicts = verify_clin_sig([variant], rows, reference=snapshot)
    assert len(conflicts) == 1
    assert (conflicts[0].authored, conflicts[0].clinvar) == ("pathogenic", "likely_benign")
    assert conflicts[0].opposed is True


# ── it reports, never repairs; and strict does not escalate ─────────────────────────────────────


def _spec(d: Path, clin_sig: str, genotype: str) -> Path:
    d.mkdir(parents=True, exist_ok=True)
    (d / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    (d / "variants.csv").write_text(
        "chrom,start,ref,alts,genotype,state,conclusion,clin_sig\n"
        f"{_CHROM},{_START},{_REF},A,{genotype},risk,c,{clin_sig}\n",
        encoding="utf-8",
    )
    (d / "studies.csv").write_text("rsid,pmid\nrs334,29165669\n", encoding="utf-8")
    return d


@pytest.mark.parametrize("mode", ["best_effort", "strict"])
def test_strict_does_not_escalate_a_clinical_disagreement(
    snapshot: Path, tmp_path: Path, mode: str
) -> None:
    """The one check whose severity deliberately does NOT follow the mode.

    Failing a strict compile here would have the format decide that ClinVar is right and the curator
    is wrong — a gene–disease judgement the data-agnostic charter keeps out of these libraries.
    """
    spec = _spec(tmp_path / mode, "benign", "A/T")
    result = enrich(spec, mode=mode, offline=True, clinvar_cache=snapshot, use_gnomad=False)

    assert len(result.clin_sig_conflicts) == 1
    assert result.clin_sig_conflicts[0].opposed is True
    # The authored value is untouched — the finding is a report, not an edit.
    assert "benign" in (spec / "variants.csv").read_text()


def test_the_check_is_skipped_when_no_snapshot_is_provisioned(tmp_path: Path) -> None:
    """A check that could not run is not a check that passed; it returns nothing and says so."""
    variant = _variant("benign", "A/T")
    assert verify_clin_sig([variant], _resolution(variant), reference=None) == []


def test_an_unusable_snapshot_degrades_instead_of_raising(tmp_path: Path) -> None:
    """Same doctrine the resolver link follows: a foreign parquet in the cache must not sink a run."""
    import polars as pl

    broken = tmp_path / "broken" / "data"
    broken.mkdir(parents=True)
    pl.DataFrame({"totally": ["unrelated"], "columns": ["here"]}).write_parquet(
        broken / "chr.parquet"
    )
    variant = _variant("benign", "A/T")
    assert verify_clin_sig([variant], _resolution(variant), reference=tmp_path / "broken") == []
