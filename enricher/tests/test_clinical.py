"""The ClinVar `clin_sig` cross-check — allele-exactness, conflict classification, and non-escalation.

Everything here runs against the committed real ClinVar slice
(``assets/clinvar_GRCh38_slice.vcf.gz``), built into a snapshot at test time. That slice happens to
contain the exact hazard this check has to survive: **`rs334` at 11:5227002 carries `T>A` as
`pathogenic` (2 stars) and `T>G` as `likely_benign` (1 star)** — one rsID, one locus, two opposite
clinical calls. A cross-check keyed on rsID would report a module that is simply right, so the
allele-exactness is not a refinement, it is the difference between a useful check and a noisy one.
"""

import csv
import io
import json
import shutil
from pathlib import Path

import pytest
from just_dna_enricher.clinical import compare_clin_sig, verify_clin_sig
from just_dna_enricher.clinvar import clinvar_dataset_label, select_by_gene
from just_dna_enricher.clinvar_build import build_snapshot
from just_dna_enricher.clinvar_draft import draft_gene_panel
from just_dna_enricher.enrich import enrich
from just_dna_enricher.licensing import CLINVAR_TERMS, merge_sources_file
from just_dna_enricher.locations import RELEASE_FILENAME
from just_dna_format.layout import SOURCES_CSV, preferred_spelling
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


# ── S4 / RM4: a module drafted from this very snapshot cannot fail this check ───────────────────
#
# The skip used to key on an authored `panel:` block. It keys on the licence row's `dataset` column
# now (RM4): the claim is *provenance* — these rows came from this snapshot — and the tool that copied
# them is the authority on it, so the enricher records it rather than asking an author to maintain a
# declaration whose only reader is this one skip. `panel:` is deprecated and reads nothing here.


def _release(snapshot: Path) -> dict:
    return json.loads((snapshot / RELEASE_FILENAME).read_text(encoding="utf-8"))


def _licenced(d: Path, clin_sig: str, genotype: str, *, dataset: str, layer: str = "annotation") -> Path:
    """`_spec` plus the licence row a ClinVar draft writes — the marker this skip keys on."""
    spec = _spec(d, clin_sig, genotype)
    merge_sources_file(
        [CLINVAR_TERMS.row(layer, declared_use="unstated", dataset=dataset)],
        spec,
        error=RuntimeError,
    )
    return spec


def test_the_label_is_the_release_the_snapshot_states(snapshot: Path, tmp_path: Path) -> None:
    """Writer and reader compute it with the same function, so they cannot drift apart silently."""
    release = _release(snapshot)
    assert clinvar_dataset_label(snapshot) == f"clinvar_{release['clinvar_file_date']}"
    # No release.json at all, and an unreadable one, are both unknowns: withheld, never a label.
    bare = tmp_path / "bare"
    bare.mkdir()
    assert clinvar_dataset_label(bare) is None
    assert clinvar_dataset_label(None) is None


def test_the_source_digest_names_the_release_when_the_file_date_does_not(
    snapshot: Path, tmp_path: Path
) -> None:
    """A VCF header that stated no file date still leaves the bytes it was built from, which name the
    release exactly. The fallback is the digest, not a gap."""
    release = _release(snapshot)
    undated = tmp_path / "undated"
    shutil.copytree(snapshot, undated)
    (undated / RELEASE_FILENAME).write_text(
        json.dumps({**release, "clinvar_file_date": None}), encoding="utf-8"
    )
    assert clinvar_dataset_label(undated) == f"clinvar_sha256:{release['source_sha256']}"


def test_a_release_label_alone_no_longer_skips_the_check(
    snapshot: Path, tmp_path: Path
) -> None:
    """The skip is a conjunction since RM73, and this is the half that used to carry it alone.

    A licence row naming this release says the rows *were* copied out of the snapshot. It says nothing
    about whether they still are — that was the hole RM4 shipped and named in its own message — so a
    row bearing the label and no drafter's digest establishes nothing about its cells and the check
    runs in full. The conflicting call is left in place deliberately: it proves the check really ran.

    Note the direction of the change. Nothing that was *checked* stopped being checked; a module that
    was being waved through on a claim is now examined.
    """
    spec = _licenced(
        tmp_path / "labelled", "benign", "A/T", dataset=clinvar_dataset_label(snapshot) or ""
    )
    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)

    assert result.clin_sig_not_checked is None
    assert [c.authored for c in result.clin_sig_conflicts] == ["benign"]


def test_a_licence_row_naming_another_release_still_runs_the_check(
    snapshot: Path, tmp_path: Path
) -> None:
    """A different release is not this one, so the comparison is real again."""
    spec = _licenced(tmp_path / "stale", "benign", "A/T", dataset="clinvar_1999-01-01")
    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)

    assert len(result.clin_sig_conflicts) == 1
    assert result.clin_sig_not_checked is None


def test_a_resolution_layer_row_is_not_a_claim_that_annotations_were_copied(
    snapshot: Path, tmp_path: Path
) -> None:
    """`enrich()` writes a second ClinVar row at the `resolution` layer for the coordinates it looked
    up. A coordinate is not a copied clinical call, so that row must not skip this check — and it is
    the row every ClinVar-resolved module ends up carrying, so keying on the source alone would
    silence the check across the whole corpus."""
    spec = _licenced(
        tmp_path / "resolution-layer", "benign", "A/T",
        dataset=clinvar_dataset_label(snapshot) or "", layer="resolution",
    )
    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)

    assert result.clin_sig_not_checked is None
    assert len(result.clin_sig_conflicts) == 1


@pytest.mark.parametrize(
    "dataset",
    [
        # Recorded, but the release is unstated: a row that says only "clinvar" establishes nothing.
        "",
        # Whitespace is the same absence wearing a value.
        "   ",
    ],
)
def test_an_unrecorded_release_is_not_permission_to_skip(
    snapshot: Path, tmp_path: Path, dataset: str
) -> None:
    """The tri-state rule: only a match skips. Absence and mismatch both mean "check it"."""
    spec = _licenced(tmp_path / f"blank{len(dataset)}", "benign", "A/T", dataset=dataset)
    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)

    assert result.clin_sig_not_checked is None
    assert len(result.clin_sig_conflicts) == 1


def test_a_panel_block_no_longer_skips_the_check(snapshot: Path, tmp_path: Path) -> None:
    """The intentional behaviour change (RM4), asserted rather than left implicit.

    A 0.5 module whose `panel:` pin matches this snapshot exactly used to skip. It does not any more:
    the block is deprecated and nothing here reads it, and the failure direction is the safe one —
    such a module gets the check *run*, never wrongly skipped.
    """
    release = _release(snapshot)
    spec = _spec(tmp_path / "panelled", "benign", "A/T")
    (spec / "module_spec.yaml").write_text(
        _YAML + f"panel:\n  source: clinvar\n  reference: '{release['clinvar_file_date']}'\n"
        f"  reference_sha256: 'sha256:{release['source_sha256']}'\n",
        encoding="utf-8",
    )
    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)

    assert result.clin_sig_not_checked is None
    assert len(result.clin_sig_conflicts) == 1


def test_a_release_the_snapshot_cannot_state_does_not_skip(snapshot: Path, tmp_path: Path) -> None:
    """An unreadable `release.json` is an unknown, and an unknown never authorizes skipping."""
    copy = tmp_path / "unreadable"
    shutil.copytree(snapshot, copy)
    label = clinvar_dataset_label(snapshot) or ""
    (copy / RELEASE_FILENAME).write_text("{not json at all", encoding="utf-8")
    spec = _licenced(tmp_path / "drafted-unreadable", "benign", "A/T", dataset=label)
    result = enrich(spec, offline=True, clinvar_cache=copy, use_gnomad=False)

    assert result.clin_sig_not_checked is None
    assert len(result.clin_sig_conflicts) == 1


# ── the hand-edit hole, and the mode ladder that closes it (RM4) ─────────────────────────────────


def _rewrite_variants(spec: Path, edit) -> list[dict]:
    """Read `variants.csv`, let `edit` change the rows, write it back. What an author's editor does."""
    rows = list(csv.DictReader(io.StringIO((spec / "variants.csv").read_text(encoding="utf-8"))))
    edit(rows)
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    (spec / "variants.csv").write_text(out.getvalue(), encoding="utf-8")
    return rows


def _fill_genotypes(spec: Path, snapshot: Path, genes: list[str]) -> None:
    """Do what the author does after a draft: decide the zygosity each finding is about.

    The genotype is built from the record the row was drafted from — heterozygous, which is what a
    ClinVar allele on a diploid contig usually describes — so nothing here fabricates a locus.
    """
    # Keyed on (rsid, clin_sig), not on the rsID alone: `rs334` names a pathogenic `T>A` *and* a
    # likely-benign `T>G` at one locus, which is the hazard this whole check is built around. Keying
    # on the rsID would hand a row the sibling allele's genotype and quietly change which variant it
    # is about — and it would do so depending on row order, which is worse.
    alleles = {
        (record["rsid"], record["clin_sig"]): (record["ref"], record["alt"])
        for record in select_by_gene(snapshot, genes, min_review_stars=0)
        if record["rsid"]
    }

    def decide(rows: list[dict]) -> None:
        for row in rows:
            # Alphabetically sorted, which is what an unphased genotype must be — the model says so
            # and the loader refuses the other order, so build it the way the format spells it.
            row["genotype"] = "/".join(sorted(alleles[(row["rsid"], row["clin_sig"])]))

    _rewrite_variants(spec, decide)


def _drafted_panel(spec: Path, snapshot: Path) -> Path:
    """A real HBB panel drafted from the slice, with the placeholders filled as an author would."""
    spec.mkdir(parents=True, exist_ok=True)
    (spec / "module_spec.yaml").write_text(_YAML, encoding="utf-8")
    result = draft_gene_panel(spec, ["HBB"], snapshot=snapshot, min_review_stars=2)
    assert result.added_for("variants.csv") > 0, result.warnings
    _fill_genotypes(spec, snapshot, ["HBB"])
    return spec


def test_drafting_records_which_release_the_rows_were_copied_out_of(
    snapshot: Path, tmp_path: Path
) -> None:
    """The whole route, through the shipped surface: the drafting pass stamps the release, and the
    check reads it back and skips itself. Neither side was told the label by the test."""
    spec = _drafted_panel(tmp_path / "panel", snapshot)
    recorded = [
        row for row in csv.DictReader(
            io.StringIO((spec / preferred_spelling(SOURCES_CSV)).read_text(encoding="utf-8"))
        )
        if row["source"] == "clinvar" and row["layer"] == "annotation"
    ]
    assert [row["dataset"] for row in recorded] == [clinvar_dataset_label(snapshot)]

    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)
    assert "drafted from" in (result.clin_sig_not_checked or "")
    assert result.clin_sig_comparison is None  # nothing was compared; the skip held


def test_widening_from_a_newer_release_withdraws_the_label_rather_than_re_labelling(
    snapshot: Path, tmp_path: Path
) -> None:
    """A second draft from a different snapshot leaves rows from two releases, and one column cannot
    name both.

    The merge that writes the licence row is never-clobber so a curator's terms survive a re-run, and
    `dataset` inherited that the moment it became load-bearing — leaving the row asserting a release
    half the rows did not come from, in the column `manifest.sources` publishes. Withdrawn, not
    re-labelled: unknown is withheld, and an empty `dataset` skips nothing, so the check simply runs.
    """
    spec = _drafted_panel(tmp_path / "panel-widened", snapshot)
    newer = tmp_path / "newer"
    shutil.copytree(snapshot, newer)
    release = _release(snapshot)
    (newer / RELEASE_FILENAME).write_text(
        json.dumps({**release, "clinvar_file_date": "2026-08-01"}), encoding="utf-8"
    )
    # A lower review floor, so the newer snapshot really does contribute rows the first draft left out.
    second = draft_gene_panel(spec, ["HBB"], snapshot=newer, min_review_stars=1)
    assert second.added_for("variants.csv") > 0, second.warnings

    licence = spec / preferred_spelling(SOURCES_CSV)
    recorded = [
        row for row in csv.DictReader(io.StringIO(licence.read_text(encoding="utf-8")))
        if row["source"] == "clinvar" and row["layer"] == "annotation"
    ]
    assert [row["dataset"] for row in recorded] == [""]
    assert any(clinvar_dataset_label(snapshot) in w for w in second.warnings)
    # The terms themselves are untouched — only the provenance cell was withdrawn.
    assert recorded[0]["license"] == "public-domain"

    # And the skip is gone with it, which is the conservative direction.
    _fill_genotypes(spec, snapshot, ["HBB"])
    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)
    assert result.clin_sig_not_checked is None


def test_a_re_draft_that_adds_nothing_leaves_the_label_alone(snapshot: Path, tmp_path: Path) -> None:
    """The provenance is about the rows, so a run that added none has nothing to be honest about."""
    spec = _drafted_panel(tmp_path / "panel-rerun", snapshot)
    newer = tmp_path / "newer-rerun"
    shutil.copytree(snapshot, newer)
    (newer / RELEASE_FILENAME).write_text(
        json.dumps({**_release(snapshot), "clinvar_file_date": "2026-08-01"}), encoding="utf-8"
    )
    again = draft_gene_panel(spec, ["HBB"], snapshot=newer, min_review_stars=2)
    assert again.added_for("variants.csv") == 0

    recorded = [
        row for row in csv.DictReader(
            io.StringIO((spec / preferred_spelling(SOURCES_CSV)).read_text(encoding="utf-8"))
        )
        if row["source"] == "clinvar" and row["layer"] == "annotation"
    ]
    assert [row["dataset"] for row in recorded] == [clinvar_dataset_label(snapshot)]


def test_strict_looks_every_row_up_and_reports_the_split(snapshot: Path, tmp_path: Path) -> None:
    """The strict arm of the ladder: no skip, and never a meaningless zero.

    Both modes skip, and that is RM73's collapse of RM4's ladder. `strict` used to pay for a per-row
    look-up here to recover the split the module-level marker could not see; the drafter's digest
    answers the same question offline, so there is nothing left for a mode to switch on.
    """
    spec = _drafted_panel(tmp_path / "panel-strict", snapshot)
    for mode in ("best_effort", "strict"):
        result = enrich(spec, mode=mode, offline=True, clinvar_cache=snapshot, use_gnomad=False)
        assert "drafted from" in (result.clin_sig_not_checked or ""), mode
        assert result.clin_sig_comparison is None, mode
        assert result.clin_sig_conflicts == [], mode


def test_a_hand_edit_re_enables_the_check_in_both_modes(
    snapshot: Path, tmp_path: Path
) -> None:
    """The hole RM4 shipped knowingly, closed (RM73).

    A cell edited after the draft is no longer a copy of anything, and no module-level fact could see
    that — so `best_effort` skipped the check entirely and the edited row went unexamined. The
    drafter's digest covers the `clin_sig` column, so the edit moves it, the skip lapses, and the
    conflict is found **without** the per-row look-up `strict` used to pay for.
    """
    spec = _drafted_panel(tmp_path / "panel-edited", snapshot)

    def disagree(rows: list[dict]) -> None:
        """A curator overrules ClinVar on the first row — call and legacy booleans together, which is
        what a coherent edit looks like."""
        assert rows[0]["clin_sig"] == "pathogenic"
        rows[0].update({"clin_sig": "benign", "pathogenic": "", "benign": "true"})

    edited = _rewrite_variants(spec, disagree)
    assert [row["clin_sig"] for row in edited[1:]] == ["pathogenic"] * (len(edited) - 1)

    for mode in ("best_effort", "strict"):
        result = enrich(spec, mode=mode, offline=True, clinvar_cache=snapshot, use_gnomad=False)
        assert result.clin_sig_not_checked is None, mode
        assert [c.authored for c in result.clin_sig_conflicts] == ["benign"], mode
        assert result.clin_sig_conflicts[0].opposed is True, mode
        # Every drafted row was compared, not just the edited one: the digest is a whole-table fact,
        # so one edit re-opens the table rather than one row. Stated because it is the cost.
        assert result.clin_sig_comparison.compared == len(edited)


def test_filling_a_genotype_stub_does_not_re_enable_the_check(
    snapshot: Path, tmp_path: Path
) -> None:
    """Why the digest is scoped to the checked COLUMN rather than the row.

    `clinvar_draft` leaves `genotype` as a placeholder the human is required to fill, so a
    whole-row hash would be invalidated by the one edit every drafted module must receive — the skip
    would never fire once. Filling the stub leaves the `clin_sig` projection untouched.
    """
    spec = _drafted_panel(tmp_path / "panel-stub", snapshot)

    def fill(rows: list[dict]) -> None:
        for row in rows:
            row["genotype"] = "A/G"

    _rewrite_variants(spec, fill)
    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)
    assert "drafted from" in (result.clin_sig_not_checked or "")


def test_a_refinement_of_the_source_re_enables_the_check_without_conflicting(
    snapshot: Path, tmp_path: Path
) -> None:
    """`likely_pathogenic` where ClinVar says `pathogenic` is a real edit and not a disagreement.

    It moves the digest — a human wrote it, so the check must look — and then reports nothing, because
    the two agree within one camp. Both halves matter: the old bucket split asserted the same thing by
    counting, and this asserts it by running the check.
    """
    spec = _drafted_panel(tmp_path / "panel-refined", snapshot)

    def refine(rows: list[dict]) -> None:
        rows[0]["clin_sig"] = "likely_pathogenic"

    _rewrite_variants(spec, refine)
    result = enrich(spec, offline=True, clinvar_cache=snapshot, use_gnomad=False)

    assert result.clin_sig_not_checked is None
    assert result.clin_sig_conflicts == []
    assert result.clin_sig_comparison is not None and result.clin_sig_comparison.compared > 0


def test_a_locus_wide_comparison_reports_no_conflict_against_a_sibling_allele(
    snapshot: Path,
) -> None:
    """The ALT could not be pinned down, so the comparison spans the whole locus.

    `rs334` carries a pathogenic `T>A` beside a likely-benign `T>G`, and a genotype naming both alts
    leaves the check unable to say which the row is about. Agreement anywhere at the locus settles it:
    reporting a conflict here would be a finding about a sibling allele's call.
    """
    variant = _variant("pathogenic", "A/G")
    comparison = compare_clin_sig([variant], _resolution(variant), reference=snapshot)

    assert comparison is not None and comparison.conflicts == []
    assert comparison.compared == 1
    # The same call on the allele the row is actually about behaves identically — the verdict never
    # depended on the provenance split that used to be counted here.
    exact = _variant("pathogenic", "A/T")
    exact_comparison = compare_clin_sig([exact], _resolution(exact), reference=snapshot)
    assert exact_comparison is not None and exact_comparison.conflicts == []
    assert exact_comparison.compared == 1


def test_a_locus_clinvar_says_nothing_about_is_counted_not_folded_in(snapshot: Path) -> None:
    """A comparison the snapshot could not answer is its own outcome.

    Folding it into `compared` would claim a comparison nobody made — the same reason an empty
    conflict list carries its reason rather than standing alone.
    """
    variant = VariantRow(
        chrom="7", start=117559590, ref="A", alts="G", genotype="A/G",
        state="risk", conclusion="c", clin_sig="pathogenic",
    )
    rows = [ResolutionRow(variant_key=variant.variant_key, chrom="7", start=117559590, ref="A",
                          alts="G", source="clinvar", status="resolved")]
    audit = compare_clin_sig([variant], rows, reference=snapshot)

    assert audit is not None
    assert (audit.no_record, audit.compared) == (1, 0)
    assert "1 had no ClinVar record" in str(audit)


def test_a_hand_authored_module_is_never_skipped_as_a_tautology(
    snapshot: Path, tmp_path: Path
) -> None:
    """A module that never claimed a draft records no digest, so nothing is established and the check
    runs in full.

    A value equal to ClinVar's is *consistent with* it; treating it as copied would assert a
    provenance nobody established — the same false-accusation rule that keeps the gene/locus check
    coarse, and the reason `drafted_unchanged` returns `None` rather than `True` when there is no
    record to compare against.
    """
    spec = _spec(tmp_path / "hand-authored", "pathogenic", "A/T")
    result = enrich(spec, mode="strict", offline=True, clinvar_cache=snapshot, use_gnomad=False)

    assert result.clin_sig_not_checked is None
    assert result.clin_sig_conflicts == []
    assert result.clin_sig_comparison is not None and result.clin_sig_comparison.compared == 1


def test_an_unusable_snapshot_says_so_rather_than_reporting_a_pass(tmp_path: Path) -> None:
    """A check that could not run is not a check that passed — and an empty conflict list alone says
    the second. `compare_clin_sig` returns `None` rather than a comparison of zeros, and the run records it."""
    import polars as pl

    broken = tmp_path / "unusable" / "data"
    broken.mkdir(parents=True)
    pl.DataFrame({"totally": ["unrelated"]}).write_parquet(broken / "chr.parquet")
    spec = _spec(tmp_path / "spec", "benign", "A/T")
    result = enrich(spec, offline=True, clinvar_cache=tmp_path / "unusable", use_gnomad=False)

    assert result.clin_sig_not_checked == "unusable_snapshot"
    assert result.clin_sig_conflicts == []


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
