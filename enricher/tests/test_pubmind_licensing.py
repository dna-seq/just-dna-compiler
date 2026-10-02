"""`PUBMIND_TERMS`, and what a module carrying PubMind values actually does at compile (RM134 § A, RM320).

Until 2026-09-28 this was the one entry in `licensing.py` whose every axis was `None`: the
ANNOVAR-distributed table published no data terms, and unknown neither taints nor permits
(`@no-named-licence`). WGLab answered in writing (WGLab/PubMind#5): the table is **CC BY-NC-ND 4.0**.
So the axes now read the way this file reads that licence for an article (`ARTICLE_TERMS_BY_LICENSE`), the
module-wide verdict is a definite `False`, and a `commercial` or `unstated` declaration refuses at
compile exactly as it does for ClinPGx. NoDerivatives has no axis and lives in `notice`.
"""

import shutil
from pathlib import Path

import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_enricher.licensing import (
    ARTICLE_TERMS_BY_LICENSE,
    PUBMIND_TERMS,
    TERMS_BY_SOURCE,
    LicenseRefusal,
    check_declared_use,
    merge_sources_file,
)
from just_dna_format.sources import taints_commercial_use, taints_redistribution
from just_dna_format.vocab import VALID_DECLARED_USE

_EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "hfe_hemochromatosis"


def _spec_with_pubmind(tmp_path: Path, *, declared_use: str = "non_commercial") -> Path:
    """A real reference module with one annotation-layer `pubmind` row appended to `sources.csv`."""
    spec = tmp_path / "spec"
    shutil.copytree(_EXAMPLE, spec)
    (spec / "verification.json").unlink(missing_ok=True)
    # Through the real writer rather than by hand: it is the one that resolves the sidecar's name and
    # quotes the cells, and a hand-rolled append is how a `notice` containing a comma shifts a column.
    merge_sources_file(
        [PUBMIND_TERMS.row("annotation", declared_use=declared_use)],
        spec,
        error=RuntimeError,
    )
    return spec


def test_the_axes_read_cc_by_nc_nd_as_this_file_reads_it_for_an_article() -> None:
    """One reading of one licence: the source constant may not drift from the per-article map."""
    assert PUBMIND_TERMS.source == "pubmind"
    assert PUBMIND_TERMS.license == "CC-BY-NC-ND-4.0"
    article = ARTICLE_TERMS_BY_LICENSE["cc by-nc-nd"]
    assert (PUBMIND_TERMS.share_alike, PUBMIND_TERMS.commercial_use, PUBMIND_TERMS.redistribution) == (
        article.share_alike,
        article.commercial_use,
        article.redistribution,
    )
    # NoDerivatives is the clause no axis carries, so the notice must; and the URL is the written answer.
    assert PUBMIND_TERMS.notice and "NoDerivatives" in PUBMIND_TERMS.notice
    assert PUBMIND_TERMS.license_url == "https://github.com/WGLab/PubMind/issues/5"
    assert TERMS_BY_SOURCE["pubmind"] is PUBMIND_TERMS


def test_a_pubmind_row_taints_commercial_use_and_not_redistribution() -> None:
    """The predicate both the compile gate and the manifest summary share, asserted directly."""
    row = PUBMIND_TERMS.row("annotation", declared_use="unstated")
    assert taints_commercial_use(row) is True
    assert taints_redistribution(row) is False


def test_the_acquisition_gate_reads_pubmind_as_a_no_sale_source() -> None:
    """Three outcomes, one per declaration, walked from the vocabulary so a new member is exercised."""
    assert set(VALID_DECLARED_USE) == {"unstated", "non_commercial", "commercial"}
    assert check_declared_use(PUBMIND_TERMS, "non_commercial") is None
    skipped = check_declared_use(PUBMIND_TERMS, "unstated")
    assert skipped is not None and "forbids sale and no use was declared" in skipped
    with pytest.raises(LicenseRefusal, match="forbid offering the data for sale"):
        check_declared_use(PUBMIND_TERMS, "commercial")


def test_a_module_carrying_pubmind_compiles_only_under_a_non_commercial_declaration(tmp_path: Path) -> None:
    """The flip RM320 declares: under null terms all three compiled; under NC only one does."""
    outcomes = {}
    for declared_use in sorted(VALID_DECLARED_USE):
        spec = _spec_with_pubmind(tmp_path / declared_use, declared_use=declared_use)
        result = compile_module(spec, tmp_path / declared_use / "art", strict=False)
        outcomes[declared_use] = (result.success, [e for e in result.errors if "licensing:" in e])
    assert outcomes["non_commercial"] == (True, [])
    for refused in ("unstated", "commercial"):
        success, errors = outcomes[refused]
        assert not success and errors and "['pubmind']" in errors[0], outcomes


def test_the_manifest_records_pubmind_as_non_commercial_rather_than_undetermined(tmp_path: Path) -> None:
    """Named in `sources`, no longer in `unknown_terms_sources`, and the layer is non-commercial."""
    spec = _spec_with_pubmind(tmp_path)
    result = compile_module(spec, tmp_path / "art", strict=False)
    assert result.success, result.errors
    sources = result.manifest.sources
    assert sources is not None
    assert "pubmind" in sources.sources
    assert "pubmind" not in sources.unknown_terms_sources
    assert sources.commercial_use is False
    assert "annotation" in sources.noncommercial_layers


def test_the_unknown_terms_skip_says_why_the_terms_are_unknown() -> None:
    """RM289 (from S99): the unknown-terms sentence read as *not recorded yet*, and a reader went looking
    for missing configuration. For every source this tier holds at `commercial_use=None` the absence is
    a probed reading, recorded in the terms' `notice`, so the skip carries that reading and its URL and
    says no declaration changes it. The leading phrase stays (`@warning-text-is-api`).
    """
    unknown = sorted(
        (terms for terms in TERMS_BY_SOURCE.values() if terms.commercial_use is None), key=lambda t: t.source
    )
    assert unknown and PUBMIND_TERMS not in unknown
    for terms in unknown:
        for declared in sorted(VALID_DECLARED_USE):
            reason = check_declared_use(terms, declared)
            assert reason is not None
            assert reason.startswith(f"{terms.source}: terms could not be established"), reason
            assert terms.notice and terms.notice in reason, reason
            assert terms.license_url and terms.license_url in reason, reason
            assert "no declared use changes" in reason, reason
