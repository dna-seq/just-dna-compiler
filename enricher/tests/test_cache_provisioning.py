"""The three caches that had a builder and nothing else — RM176.

ACMG's secondary-findings list, STRchive's repeat catalogue and the ClinPGx drug-label archive were
all *buildable* and all *unreachable*: each check took an explicit path and looked nowhere else, so
the only way to run one against a built snapshot was to name it on every invocation. On a deployment
that provisions caches centrally the path actually taken is the one with no flags, and for all three
that path did something worse than fail. ACMG's fell through to scraping NCBI's page, which still
serves **v3.2** while the snapshot holds v3.3 — a correctly authored row reported as wrong. The other
two skipped themselves with `no_reference`, which reads as *nobody provisioned a catalogue* about a
catalogue sitting in the cache directory.

**So the assertions here are about the call, not about the resolver.** A resolver nothing calls is
dead code that passes its own unit test (`@ensure-must-be-called`), and that is precisely the state
these three were in from the other end. Each test below builds a real snapshot from the repository's
own asset, points the lane's environment variable at it, and then runs the check **with no snapshot
argument at all**.
"""

import shutil
import zipfile
from pathlib import Path

import pytest
from just_dna_enricher import locations
from just_dna_enricher.acmg import load_acmg_snapshot, verify_acmg_sf
from just_dna_enricher.acmg_build import build_acmg_snapshot
from just_dna_enricher.drug_labels import check_drug_labels
from just_dna_enricher.drug_labels_build import build_drug_label_snapshot
from just_dna_enricher.strchive import check_repeat_bands
from just_dna_enricher.strchive_build import build_strchive_snapshot
from just_dna_format.spec import VariantRow

_ROOT = Path(__file__).resolve().parents[2]
_ASSETS = _ROOT / "assets"
_EXAMPLES = _ROOT / "reference_examples"


def _row(gene: str, *, acmg_sf: bool) -> VariantRow:
    """The minimum a `variants.csv` row has to state, with the two cells this check reads."""
    return VariantRow(
        rsid="rs1", genotype="A/A", state="risk", conclusion="x", gene=gene, acmg_sf=acmg_sf,
    )


def _module(tmp_path: Path, name: str) -> Path:
    dest = tmp_path / name
    shutil.copytree(_EXAMPLES / name, dest)
    return dest


# ── the resolvers, over the two snapshot shapes ─────────────────────────────────────────────────
#
# Two of these three snapshots hold no parquet, which is why they went unresolved for as long as they
# did: every cache that had a resolver was `data/*.parquet` and the predicate was written for that.


@pytest.fixture
def acmg_snapshot(tmp_path: Path) -> Path:
    openpyxl = pytest.importorskip("openpyxl")
    del openpyxl
    return build_acmg_snapshot(
        _ASSETS / "acmg_sf_v3.3.xlsx", tmp_path / "acmg_sf",
        source_url="file://acmg_sf_v3.3.xlsx",
    ) and (tmp_path / "acmg_sf")


@pytest.fixture
def strchive_snapshot(tmp_path: Path) -> Path:
    result = build_strchive_snapshot(
        tmp_path / "strchive", catalogue=_ASSETS / "strchive_loci_slice.json", release="v0.0.1",
    )
    return result.catalogue_file.parent


@pytest.fixture
def drug_labels_snapshot(tmp_path: Path) -> Path:
    pytest.importorskip("polars")
    archive = tmp_path / "drugLabels.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as handle:
        for path in sorted((_ASSETS / "clinpgx_drug_labels_slice").iterdir()):
            handle.write(path, path.name)
    return build_drug_label_snapshot(
        archive, tmp_path / "drug_labels", source_url="file://clinpgx_drug_labels_slice",
    ).out_dir


def test_the_cache_base_places_all_three_where_the_resolvers_look(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    acmg_snapshot: Path, strchive_snapshot: Path, drug_labels_snapshot: Path,
) -> None:
    """One `$JUST_DNA_PIPELINES_CACHE_DIR` serves all three, like every cache that came before them.

    The subdirectory names are read off `locations` rather than typed in: the resolver and the layout
    constant are the two halves that have to agree, and a test spelling the directory itself would
    pass while they disagreed.
    """
    base = tmp_path / "base"
    for subdir, built in (
        (locations.ACMG_SUBDIR, acmg_snapshot),
        (locations.STRCHIVE_SUBDIR, strchive_snapshot),
        (locations.DRUG_LABELS_SUBDIR, drug_labels_snapshot),
    ):
        shutil.copytree(built, base / subdir)
    monkeypatch.setenv("JUST_DNA_PIPELINES_CACHE_DIR", str(base))

    assert locations.resolve_acmg_reference() == base / locations.ACMG_SUBDIR
    assert locations.resolve_strchive_reference() == base / locations.STRCHIVE_SUBDIR
    assert locations.resolve_drug_labels_reference() == base / locations.DRUG_LABELS_SUBDIR


def test_a_bare_catalogue_file_still_resolves_and_a_wrong_name_does_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Pointing straight at `STRchive-loci.json` worked before the resolver existed and still does.

    The name is checked rather than the suffix: `--catalogue` used to accept any path and hand it to
    the loader, so a resolver that took any `.json` would turn a mistyped path into a load error
    somewhere else instead of an honest `None`.
    """
    payload = tmp_path / locations.STRCHIVE_CATALOGUE_FILENAME
    shutil.copyfile(_ASSETS / "strchive_loci_slice.json", payload)
    monkeypatch.setenv("JUST_DNA_STRCHIVE_CACHE", str(payload))
    assert locations.resolve_strchive_reference() == payload

    misnamed = tmp_path / "loci.json"
    shutil.copyfile(payload, misnamed)
    monkeypatch.setenv("JUST_DNA_STRCHIVE_CACHE", str(misnamed))
    assert locations.resolve_strchive_reference() is None


# ── the calls: each check reaches the cache with no flag ─────────────────────────────────────────


def test_acmg_offline_reads_a_provisioned_snapshot_instead_of_reporting_unchecked(
    monkeypatch: pytest.MonkeyPatch, acmg_snapshot: Path,
) -> None:
    """`--offline` with no `--sf-list` used to check nothing at all, snapshot present or not.

    The verdict, not merely the absence of the warning: a row naming a gene the built list carries
    has to come back *checked*, and the report has to be able to name the version it checked against.
    """
    monkeypatch.setenv("JUST_DNA_ACMG_CACHE", str(acmg_snapshot))
    # The gene is taken from the built snapshot itself, so this asserts nothing about which genes
    # ACMG happens to list — only that a listed one comes back checked.
    listed = sorted(load_acmg_snapshot(acmg_snapshot).genes)
    report = verify_acmg_sf([_row(listed[0], acmg_sf=True)], offline=True)
    assert report.version is not None, "the snapshot's own version, not a scrape's"
    assert [v.verdict for v in report.verdicts] != ["unchecked"], report.warnings


def test_acmg_without_the_cache_really_did_report_unchecked(
    monkeypatch: pytest.MonkeyPatch, acmg_snapshot: Path,
) -> None:
    """The old behaviour, demonstrated rather than asserted about — the snapshot is simply unfound."""
    monkeypatch.setenv("JUST_DNA_ACMG_CACHE", str(acmg_snapshot / "nowhere"))
    monkeypatch.setenv("JUST_DNA_PIPELINES_CACHE_DIR", str(acmg_snapshot / "nowhere"))
    report = verify_acmg_sf([_row("BRCA1", acmg_sf=True)], offline=True)
    assert [v.verdict for v in report.verdicts] == ["unchecked"]


def test_repeat_bands_compares_against_a_provisioned_catalogue_with_no_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, strchive_snapshot: Path,
) -> None:
    monkeypatch.setenv("JUST_DNA_STRCHIVE_CACHE", str(strchive_snapshot))
    result = check_repeat_bands(_module(tmp_path, "htt_repeat_expansion"), write=False)
    assert result.compared, f"nothing was compared: {result.warnings}"
    assert result.dataset == "strchive_v0.0.1", "and it can name the release it compared against"


def test_repeat_bands_still_says_nobody_provisioned_one_when_nobody_did(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unreachable is not absent: with no catalogue anywhere the skip must stay, and say so."""
    monkeypatch.setenv("JUST_DNA_STRCHIVE_CACHE", str(tmp_path / "nowhere"))
    monkeypatch.setenv("JUST_DNA_PIPELINES_CACHE_DIR", str(tmp_path / "nowhere"))
    result = check_repeat_bands(_module(tmp_path, "htt_repeat_expansion"), write=False)
    assert not result.compared
    assert any("no STRchive catalogue was provisioned" in w for w in result.warnings)


def test_drug_labels_reads_a_provisioned_snapshot_with_no_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, drug_labels_snapshot: Path,
) -> None:
    monkeypatch.setenv("JUST_DNA_DRUG_LABELS_CACHE", str(drug_labels_snapshot))
    result = check_drug_labels(
        _module(tmp_path, "cyp2c19_star_alleles"), declared_use="non-commercial", write=False,
    )
    assert result.not_checked != "no_reference", result.warnings
    assert result.regulators, "a snapshot was read, so the agencies in it are known"
