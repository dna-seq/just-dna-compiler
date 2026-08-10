"""The ClinVar `clin_sig` cross-check — allele-exactness, conflict classification, and non-escalation.

Everything here runs against the committed real ClinVar slice
(``assets/clinvar_GRCh38_slice.vcf.gz``), built into a snapshot at test time. That slice happens to
contain the exact hazard this check has to survive: **`rs334` at 11:5227002 carries `T>A` as
`pathogenic` (2 stars) and `T>G` as `likely_benign` (1 star)** — one rsID, one locus, two opposite
clinical calls. A cross-check keyed on rsID would report a module that is simply right, so the
allele-exactness is not a refinement, it is the difference between a useful check and a noisy one.
"""

import json
import shutil
from pathlib import Path

import pytest
from just_dna_enricher.clinical import verify_clin_sig
from just_dna_enricher.clinvar_build import build_snapshot
from just_dna_enricher.enrich import enrich
from just_dna_enricher.locations import RELEASE_FILENAME
from just_dna_format.resolution import ResolutionRow
from just_dna_format.spec import VariantRow

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


# ── S4: a module drafted from this very snapshot cannot fail this check ─────────────────────────


def _release(snapshot: Path) -> dict:
    return json.loads((snapshot / RELEASE_FILENAME).read_text(encoding="utf-8"))


def _panel_spec(d: Path, clin_sig: str, genotype: str, panel: str) -> Path:
    """`_spec` plus an authored `panel:` block — the RM4 declaration this skip keys on."""
    spec = _spec(d, clin_sig, genotype)
    (d / "module_spec.yaml").write_text(_YAML + panel, encoding="utf-8")
    return spec


def test_the_check_is_skipped_when_the_module_was_drafted_from_this_release(
    snapshot: Path, tmp_path: Path
) -> None:
    """The pin matches the snapshot, so every authored `clin_sig` is a copy of what it is compared to.

    Without the skip this reports a confident "0 conflicts" that no data could have made non-zero —
    which reads as evidence and is not. The conflicting call is deliberately left in place: it proves
    the check really was skipped rather than merely finding nothing.
    """
    release = _release(snapshot)
    spec = _panel_spec(
        tmp_path / "pinned", "benign", "A/T",
        f"panel:\n  source: clinvar\n  reference: '{release['clinvar_file_date']}'\n"
        f"  reference_sha256: 'sha256:{release['source_sha256']}'\n",
    )
    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)

    assert result.clin_sig_conflicts == []
    assert "drafted from the very snapshot" in (result.clin_sig_not_checked or "")
    # Same module without the declaration: the check runs and finds the disagreement.
    unpinned = enrich(
        _spec(tmp_path / "unpinned", "benign", "A/T"),
        offline=True, clinvar_cache=snapshot, use_gnomad=False,
    )
    assert len(unpinned.clin_sig_conflicts) == 1
    assert unpinned.clin_sig_not_checked is None


def test_a_pin_on_another_release_still_runs_the_check(snapshot: Path, tmp_path: Path) -> None:
    """A different release is not this one, so the comparison is real again — and one byte is enough."""
    release = _release(snapshot)
    spec = _panel_spec(
        tmp_path / "stale", "benign", "A/T",
        f"panel:\n  source: clinvar\n  reference: '{release['clinvar_file_date']}'\n"
        f"  reference_sha256: 'sha256:{'0' + release['source_sha256'][1:]}'\n",
    )
    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)

    assert len(result.clin_sig_conflicts) == 1
    assert result.clin_sig_not_checked is None


@pytest.mark.parametrize(
    "panel",
    [
        # No pin at all — a panel that declares its source and nothing else establishes nothing.
        "panel:\n  source: clinvar\n",
        # A panel over some other reference: this snapshot is not what it was drafted from.
        "panel:\n  source: pharmvar\n  reference: '2026-06-27'\n",
    ],
)
def test_an_unestablished_pin_is_not_permission_to_skip(
    snapshot: Path, tmp_path: Path, panel: str
) -> None:
    """The tri-state rule: only a match skips. Absence and mismatch both mean "check it"."""
    spec = _panel_spec(tmp_path / str(abs(hash(panel))), "benign", "A/T", panel)
    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)

    assert result.clin_sig_not_checked is None
    assert len(result.clin_sig_conflicts) == 1


def test_a_release_the_snapshot_cannot_state_does_not_skip(snapshot: Path, tmp_path: Path) -> None:
    """An unreadable `release.json` is an unknown, and an unknown never authorizes skipping."""
    release = _release(snapshot)
    copy = tmp_path / "unreadable"
    shutil.copytree(snapshot, copy)
    (copy / RELEASE_FILENAME).write_text("{not json at all", encoding="utf-8")
    spec = _panel_spec(
        tmp_path / "pinned-unreadable", "benign", "A/T",
        f"panel:\n  source: clinvar\n  reference: '{release['clinvar_file_date']}'\n",
    )
    result = enrich(spec, offline=True, clinvar_cache=copy, use_gnomad=False)

    assert result.clin_sig_not_checked is None
    assert len(result.clin_sig_conflicts) == 1


def test_not_running_the_check_is_distinguishable_from_running_it(
    snapshot: Path, tmp_path: Path
) -> None:
    """An empty conflict list means two opposite things, so the reason travels beside it."""
    spec = _spec(tmp_path / "off", "pathogenic", "A/T")
    off = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False, verify_clinsig=False)
    on = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)
    none = enrich(spec, offline=True, clinvar_cache=tmp_path / "nothing-here", use_gnomad=False)

    assert (off.clin_sig_conflicts, off.clin_sig_not_checked) == ([], "not_requested")
    assert (on.clin_sig_conflicts, on.clin_sig_not_checked) == ([], None)
    assert (none.clin_sig_conflicts, none.clin_sig_not_checked) == ([], "no_snapshot")


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
