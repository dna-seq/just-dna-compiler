"""RM369: no builder leaves a `release.json` describing bytes it has replaced.

Every builder swapped its payload in and wrote `release.json` after it. A build that died between the
two (a full disk, a killed process) left the new bytes under the previous build's record, which every
reader believes: the label `cache status` prints, the `dataset` a pass stamps onto `SourceRow`, a
child's parent pin. `begin_snapshot_write` withdraws the record before the payload moves, and its
handle writes the new one last, so the worst case is a snapshot that states no release, an unknown,
rather than one that states the wrong one.

Each builder is run here for real, offline, over the fixtures its own tests use, against a directory
that already holds a described snapshot, and checked at the two moments that matter:

- **when the record is withdrawn**, nothing a reader globs has moved yet (a withdrawal placed after the
  payload write would leave the old window open);
- **when the describe step fails**, no `release.json` is left behind.

The walk is an equality: the builders run here plus the ones exempted with a reason are exactly the
`*_build.py` modules, so a new builder fails here until someone runs it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from collections.abc import Callable
from pathlib import Path

import httpx
import just_dna_enricher
import polars as pl
import pytest
from just_dna_enricher import (
    acmg_build,
    alphagenome_avi_build,
    civic_build,
    clinpgx_build,
    clinvar_build,
    clinvar_gkm_build,
    constraint_build,
    cpic_build,
    drug_labels_build,
    mane_build,
    mitomap_build,
    mitomap_miss_build,
    opentargets_build,
    pharmvar_build,
    pubmind_build,
    strchive_build,
)
from just_dna_enricher.clinvar_gkm import ALLELE_FILE, VARIATION_FILE, GkmManifest, parse_manifest
from just_dna_enricher.cpic import CpicClient
from just_dna_enricher.pharmvar import PharmVarClient
from just_dna_format import snapshot
from just_dna_format.snapshot import RELEASE_FILENAME, SnapshotRelease, write_release

_ROOT = Path(__file__).resolve().parents[2]
_ASSETS = _ROOT / "assets"
_PACKAGE = Path(just_dna_enricher.__file__).resolve().parent

#: Staging names a builder may write beside the live payload before it withdraws the record: no reader
#: globs them (`data/*.parquet`, a root `*.parquet`, a named payload file).
_STAGING_SUFFIXES = (".building", ".incoming", ".part")

_PLANTED = SnapshotRelease(dataset="planted_by_the_test")


def _visible(directory: Path) -> dict[str, int]:
    """Every file a reader could see under `directory`, with its mtime: staging and hidden names excluded."""
    seen: dict[str, int] = {}
    for path in directory.rglob("*"):
        relative = path.relative_to(directory)
        if not path.is_file() or relative.name == RELEASE_FILENAME:
            continue
        if any(part.startswith(".") or part.endswith(_STAGING_SUFFIXES) for part in relative.parts):
            continue
        seen[relative.as_posix()] = path.stat().st_mtime_ns
    return seen


def _plant(out_dir: Path) -> dict[str, int]:
    """A described snapshot already in place: one payload file and the record describing it."""
    (out_dir / "data").mkdir(parents=True)
    (out_dir / "data" / "planted.parquet").write_bytes(b"PAR1planted")
    write_release(out_dir, _PLANTED)
    return _visible(out_dir)


# ── how each builder is run offline ─────────────────────────────────────────────────────────────


def _zip(directory: Path, dest: Path) -> Path:
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(directory.iterdir()):
            archive.write(path, path.name)
    return dest


def _opentargets_mirror(source: Path) -> Path:
    """The smallest mirror `opentargets_build.build_snapshot` reads: one part per dataset, one row each."""
    tables = {
        "variant": pl.DataFrame(
            {
                "variantId": ["1_100_A_G"],
                "chromosome": ["1"],
                "position": [100],
                "referenceAllele": ["A"],
                "alternateAllele": ["G"],
                "rsIds": [["rs1"]],
                "transcriptConsequences": [
                    [
                        {
                            "transcriptId": "ENST1",
                            "targetId": "ENSG1",
                            "approvedSymbol": "G1",
                            "variantFunctionalConsequenceIds": ["SO:0001583"],
                            "impact": "MODERATE",
                            "maneSelect": True,
                            "isEnsemblCanonical": True,
                        }
                    ]
                ],
            }
        ),
        "credible_set": pl.DataFrame(
            {
                "studyLocusId": ["L1"],
                "studyId": ["S1"],
                "variantId": ["1_100_A_G"],
                "studyType": ["gwas"],
                "finemappingMethod": ["SuSiE-inf"],
                "confidence": ["SuSiE fine-mapped credible set with in-sample LD"],
                "locus": [[{"variantId": "1_100_A_G", "posteriorProbability": 0.9}]],
            }
        ),
        "l2g_prediction": pl.DataFrame({"studyLocusId": ["L1"], "geneId": ["ENSG1"], "score": [0.8]}),
        "study": pl.DataFrame({"studyId": ["S1"], "geneId": [None], "biosampleId": [None]}),
        "colocalisation": pl.DataFrame(
            {
                "leftStudyLocusId": ["L1"],
                "rightStudyLocusId": ["L1"],
                "rightStudyType": ["eqtl"],
                "colocalisationMethod": ["COLOC"],
                "h4": [0.9],
                "clpp": [None],
                "numberColocalisingVariants": [1],
            }
        ),
    }
    for dataset, frame in tables.items():
        (source / dataset).mkdir(parents=True)
        frame.write_parquet(source / dataset / "part-00000.parquet")
    return source


_GKM = _ASSETS / "clinvar_gkm_slice"


def _gkm_slice_manifest() -> GkmManifest:
    """The real manifest with the two inputs rewritten to the slice's own size and digest, as its tests do."""
    raw = json.loads((_GKM / "manifest.json").read_text(encoding="utf-8"))
    for entry in raw["files"]:
        if entry["name"] in (ALLELE_FILE, VARIATION_FILE):
            body = (_GKM / entry["name"]).read_bytes()
            entry["size"] = len(body)
            entry["sha256"] = hashlib.sha256(body).hexdigest()
    return parse_manifest(json.dumps(raw))


def _cpic_client() -> CpicClient:
    def handler(request: httpx.Request) -> httpx.Response:
        # Each answer states its count, as the service does: since RM361 a CPIC read with no
        # `Content-Range` refuses rather than write a snapshot that may be short.
        if request.url.path.endswith("/gene"):
            return httpx.Response(
                200, json=[{"symbol": "CYP2C19", "chr": "chr10"}], headers={"Content-Range": "0-0/1"}
            )
        return httpx.Response(200, json=[], headers={"Content-Range": "*/0"})

    return CpicClient(client=httpx.Client(transport=httpx.MockTransport(handler)))


def _pharmvar_client() -> PharmVarClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[{"geneSymbol": "CYP2C19", "alleles": []}])

    return PharmVarClient(
        api_key="a-key-for-the-test", client=httpx.Client(transport=httpx.MockTransport(handler))
    )


def _clinvar_citations(inputs: Path, out_dir: Path, request: pytest.FixtureRequest) -> None:
    text = "#AlleleID\tVariationID\trs\tnsv\tcitation_source\tcitation_id\n15041\t2\t\t\tPubMed\t20613862\n"
    path = inputs / "var_citations.txt"
    path.write_text(text, encoding="utf-8")
    clinvar_build.build_citations(path, out_dir)


#: builder module → how to run it, given an inputs directory, the snapshot directory and the request.
_RUNS: dict[str, Callable[[Path, Path, pytest.FixtureRequest], object]] = {
    "acmg_build": lambda i, o, r: acmg_build.build_acmg_snapshot(_ASSETS / "acmg_sf_v3.3.xlsx", o),
    "alphagenome_avi_build": lambda i, o, r: alphagenome_avi_build.build_snapshot(
        _ASSETS / "alphagenome" / "avi_chr22_slice.tsv.gz",
        o,
        workers=1,
        hash_source=False,
        terms_file=_ROOT / "docs" / "vendor" / "alphagenome_output_terms.txt",
    ),
    "civic_build": lambda i, o, r: civic_build.build_snapshot(
        _ASSETS / "civic_slice" / "ClinicalEvidenceSummaries.tsv",
        _ASSETS / "civic_slice" / "VariantSummaries.tsv",
        _ASSETS / "civic_slice" / "MolecularProfileSummaries.tsv",
        o,
        release="01-Aug-2026",
    ),
    "clinpgx_build": lambda i, o, r: clinpgx_build.build_snapshot(
        _zip(_ASSETS / "clinpgx_annotations_slice", i / "clinpgx.zip"), o
    ),
    "clinvar_build": lambda i, o, r: clinvar_build.build_snapshot(_ASSETS / "clinvar_GRCh38_slice.vcf.gz", o),
    "clinvar_gkm_build": lambda i, o, r: clinvar_gkm_build.build_snapshot(
        _GKM / ALLELE_FILE, _GKM / VARIATION_FILE, o, manifest=_gkm_slice_manifest()
    ),
    "constraint_build": lambda i, o, r: constraint_build.build_snapshot(
        _ASSETS / "gnomad_v4.1_constraint_slice.tsv", o
    ),
    "cpic_build": lambda i, o, r: cpic_build.build_snapshot(o, client=_cpic_client()),
    "drug_labels_build": lambda i, o, r: drug_labels_build.build_drug_label_snapshot(
        _zip(_ASSETS / "clinpgx_drug_labels_slice", i / "drugLabels.zip"), o
    ),
    "mane_build": lambda i, o, r: mane_build.build_snapshot(
        {
            "summary": _ASSETS / "mane_slice" / "MANE.GRCh38.v1.5.summary_slice.txt.gz",
            "changed_select_accessions": _ASSETS
            / "mane_slice"
            / "MANE.GRCh38.v1.5.changed_select_accessions.txt.gz",
            "protein_coding_genes_not_in_mane": _ASSETS
            / "mane_slice"
            / "MANE.GRCh38.v1.5.protein_coding_genes_not_in_mane.txt.gz",
        },
        o,
        versions_file=_ASSETS / "mane_slice" / "README_versions.txt",
    ),
    "mitomap_build": lambda i, o, r: mitomap_build.build_snapshot(r.getfixturevalue("mitomap_dump"), o),
    "mitomap_miss_build": lambda i, o, r: mitomap_miss_build.build_miss_snapshot(
        r.getfixturevalue("mitomap_snapshot"), r.getfixturevalue("tmp_path") / "clinvar", o
    ),
    "opentargets_build": lambda i, o, r: opentargets_build.build_snapshot(
        _opentargets_mirror(i / "mirror"), o
    ),
    "pharmvar_build": lambda i, o, r: pharmvar_build.build_snapshot(o, client=_pharmvar_client()),
    "pubmind_build": lambda i, o, r: pubmind_build.build_snapshot(
        _ASSETS / "hg38_pubmind_db_slice.txt.gz", o
    ),
    "strchive_build": lambda i, o, r: strchive_build.build_strchive_snapshot(
        o, catalogue=_ASSETS / "strchive_loci_slice.json", release="v0.0.1"
    ),
}

#: A second entry point of a builder module that writes a whole snapshot. ClinVar's citations half
#: writes one block of the record and has its own test below.
_ALSO: dict[str, Callable[[Path, Path, pytest.FixtureRequest], object]] = {
    "opentargets_build.subset_snapshot": lambda i, o, r: opentargets_build.subset_snapshot(
        _ASSETS / "opentargets_slice", o, [("1", 109275908, "C", "T")]
    ),
}

#: A builder no offline run reaches, with the reason. Empty: every builder is run.
_EXEMPT: dict[str, str] = {}


def test_every_builder_is_run_or_exempted_with_a_reason() -> None:
    assert set(_RUNS) | set(_EXEMPT) == {path.stem for path in _PACKAGE.glob("*_build.py")}
    assert not set(_RUNS) & set(_EXEMPT)


def _needs(name: str) -> None:
    if name == "alphagenome_avi_build" and shutil.which("tabix") is None:  # pragma: no cover
        pytest.skip("tabix is not on PATH")


@pytest.mark.parametrize(
    ("name", "run"), [*_RUNS.items(), *_ALSO.items()], ids=lambda v: v if isinstance(v, str) else ""
)
def test_the_record_is_withdrawn_before_the_payload_moves_and_a_failed_describe_leaves_none(
    name: str,
    run: Callable,
    tmp_path: Path,
    request: pytest.FixtureRequest,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _needs(name)
    inputs, out_dir = tmp_path / "inputs", tmp_path / "snap"
    inputs.mkdir()
    planted = _plant(out_dir)
    # Parents (`mitomap_miss`'s) are built through their own builders before anything is patched; the
    # run then reads them where `build_clinvar_mt` put them.
    if name == "mitomap_miss_build":
        request.getfixturevalue("mitomap_snapshot")
        request.getfixturevalue("build_clinvar_mt")()

    at_withdrawal: list[dict[str, int]] = []
    withdraw = getattr(snapshot, "_withdraw", None)

    def watching(directory: Path) -> None:
        at_withdrawal.append(_visible(Path(directory)))
        assert withdraw is not None
        withdraw(directory)

    def failing(path: Path, text: str, **kwargs: object) -> Path:
        if Path(path).name == RELEASE_FILENAME:
            raise OSError(28, "No space left on device")
        return original(path, text, **kwargs)

    original = snapshot.atomic_write_text
    monkeypatch.setattr(snapshot, "_withdraw", watching, raising=False)
    monkeypatch.setattr(snapshot, "atomic_write_text", failing)

    with pytest.raises(OSError, match="No space left"):
        run(inputs, out_dir, request)

    assert not (out_dir / RELEASE_FILENAME).exists(), (
        f"{name}: the describe step failed and the previous build's release.json still describes "
        f"{out_dir}, whose payload this build replaced"
    )
    assert at_withdrawal, f"{name}: the record was never withdrawn"
    assert at_withdrawal[0] == planted, (
        f"{name}: the payload moved before the record was withdrawn: "
        f"{sorted(set(at_withdrawal[0].items()) ^ set(planted.items()))}"
    )


def test_a_citations_build_withdraws_its_block_and_keeps_the_records(
    tmp_path: Path, request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second half of the ClinVar lane owns one block of the record, never the record."""
    inputs, out_dir = tmp_path / "inputs", tmp_path / "snap"
    inputs.mkdir()
    out_dir.mkdir()
    write_release(out_dir, SnapshotRelease(dataset="clinvar_2026-06-27", citations={"row_count": 99}))
    original = snapshot.atomic_write_text
    writes: list[str] = []

    def failing_second(path: Path, text: str, **kwargs: object) -> Path:
        # The first write withdraws the block; the second is the describe step, and it fails.
        if Path(path).name == RELEASE_FILENAME:
            writes.append(text)
            if len(writes) > 1:
                raise OSError(28, "No space left on device")
        return original(path, text, **kwargs)

    monkeypatch.setattr(snapshot, "atomic_write_text", failing_second)
    with pytest.raises(OSError, match="No space left"):
        _clinvar_citations(inputs, out_dir, request)
    release = snapshot.read_release(out_dir)
    assert release is not None
    assert release.dataset == "clinvar_2026-06-27"
    assert "citations" not in (release.model_extra or {})


def test_a_completed_build_is_described_by_its_own_record(tmp_path: Path) -> None:
    """The window closes: a build that finishes leaves its own record, never the planted one."""
    out_dir = tmp_path / "snap"
    _plant(out_dir)
    built = strchive_build.build_strchive_snapshot(
        out_dir, catalogue=_ASSETS / "strchive_loci_slice.json", release="v0.0.1"
    )
    label = snapshot.release_label(out_dir)
    assert label is not None and label != _PLANTED.dataset
    assert label == built.dataset
