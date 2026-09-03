"""A ClinVar rebuild builds the citations half too, or it reports failed (RM179).

The incident: on 2026-09-03 the published `just-dna-seq/clinvar` held records from ClinVar 2026-08-29
beside a `citations/citations.parquet` built from 2026-06-27, and its `release.json` said nothing about
the pair — the `citations` block that had described it (revision `8f5c5720`) was gone. Nobody deleted
it. `_rebuild_clinvar` built the VCF half only, `release.json` is written by that half, and the
publisher adds without deleting: so a rebuild-and-publish wrote a fresh, citations-free provenance over
a repo whose sidecar it had not replaced. Every rebuild would have repeated it.

Network-free: the VCF comes from the real repository slice through `--source`, and the one function
that would reach ClinVar is replaced by one that writes the fixture TSV. `build_citations` itself runs
for real, because the assertion that matters is what it merges into `release.json`.
"""

import json
from pathlib import Path

import pytest
from just_dna_enricher import caches
from just_dna_enricher.caches import CACHE_LANES, RebuildRequest
from just_dna_enricher.clinvar_build import ClinVarBuildError
from just_dna_enricher.locations import CITATIONS_DIRNAME, RELEASE_FILENAME

FIXTURE = Path(__file__).resolve().parents[2] / "assets" / "clinvar_GRCh38_slice.vcf.gz"

#: The same shape `test_clinvar.py` uses: two PubMed rows and one that is not PubMed.
_CITATIONS_TSV = (
    "#AlleleID\tVariationID\trs\tnsv\tcitation_source\tcitation_id\torganization_ids\n"
    "15041\t2\t397704705\t\tPubMed\t20613862\t1,3\n"
    "15041\t2\t397704705\t\tPubMed\t20613861\t1\n"
    "15042\t3\t\t\tPubMedBookArticle\t99999999\t1\n"
)

_LANE = next(lane for lane in CACHE_LANES if lane.name == "clinvar")


@pytest.fixture
def offline_citations(monkeypatch):
    """Replace the one network call with a writer of the fixture TSV, or with a failure."""

    def install(fail: Exception | None = None):
        def fake(dest: Path, url: str | None = None):
            if fail is not None:
                raise fail
            dest = Path(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(_CITATIONS_TSV, encoding="utf-8")
            return dest, "sha-of-the-fixture"

        monkeypatch.setattr(caches.clinvar_build, "download_var_citations", fake)

    return install


def _rebuild(out_dir: Path):
    return _LANE.rebuild(RebuildRequest(out_dir=out_dir, source=FIXTURE))


def test_a_rebuild_produces_the_sidecar_and_a_release_that_describes_it(
    offline_citations, tmp_path: Path
) -> None:
    """Both halves on disk, and `release.json` documenting both — the property that was missing."""
    offline_citations()
    out = tmp_path / "clinvar"
    outcome = _rebuild(out)

    assert outcome.built is True, outcome.detail
    assert (out / CITATIONS_DIRNAME / "citations.parquet").is_file()

    release = json.loads((out / RELEASE_FILENAME).read_text(encoding="utf-8"))
    # the VCF half's own provenance survives the merge …
    assert release["clinvar_file_date"]
    assert release["record_count"] > 0
    # … and the citations half is described beside it rather than silently shipped
    assert release["citations"]["row_count"] == 2, release["citations"]
    assert release["citations"]["source_sha256"] == "sha-of-the-fixture"
    # the count reaches the operator too, since the detail line is all a rebuild run prints
    assert "2 citation links" in outcome.detail


def test_the_published_shape_is_what_a_publish_would_carry(offline_citations, tmp_path: Path) -> None:
    """The plan the publisher derives must include the sidecar, which is what closes the loop.

    `plan_reference_snapshot` reads the built directory, so a snapshot with no `citations/` produces a
    plan with no sidecar and a `release.json` that describes none — the artifact that went out.
    """
    from just_dna_enricher.upload import plan_reference_snapshot

    offline_citations()
    out = tmp_path / "clinvar"
    _rebuild(out)

    plan = plan_reference_snapshot(out, "just-dna-seq/clinvar")
    assert f"{CITATIONS_DIRNAME}/citations.parquet" in plan.files
    assert RELEASE_FILENAME in plan.files


def test_a_failed_citations_half_fails_the_lane_rather_than_publishing_half_an_artifact(
    offline_citations, tmp_path: Path
) -> None:
    """`cache rebuild --publish` uploads only on `built is True`, so this is what stops the incident.

    Reporting success here would leave exactly the artifact that caused it: records from one release,
    a `release.json` describing only them, and a remote sidecar from another that nothing replaced.
    """
    offline_citations(fail=ClinVarBuildError("ClinVar is unreachable"))
    out = tmp_path / "clinvar"
    outcome = _rebuild(out)

    assert outcome.built is False
    assert outcome.out_dir is None, "an out_dir is what --publish uploads"
    assert "citations" in outcome.detail
    # the records did build, and saying so is the difference between "retry the pair" and "it broke"
    assert "the records built" in outcome.detail
    assert (out / "data").is_dir()


def test_the_vcf_half_still_reports_its_own_failure_as_itself(tmp_path: Path) -> None:
    """The first half's contract is unchanged: a missing input is that failure, not the citations one."""
    outcome = _LANE.rebuild(
        RebuildRequest(out_dir=tmp_path / "clinvar", source=tmp_path / "nothing-here.vcf.gz")
    )
    assert outcome.built is False
    assert "citations" not in outcome.detail
