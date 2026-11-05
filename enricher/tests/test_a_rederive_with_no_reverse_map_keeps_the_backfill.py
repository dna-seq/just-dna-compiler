"""RM393: a re-derivation that reads no position→rsID map keeps a positional row's back-filled rsID.

Measured by the 0.8 audit, round 3, on a copy of `reference_examples/hfe_hemochromatosis`: its two
coordinate-only rows (`ga4gh:VA.*`) carry `rs773443949`, back-filled from the Ensembl snapshot. An
`enrich --rederive` with no Ensembl and no ClinVar snapshot (a bare machine under `--offline`, or a
failed 14.5 GB pull) wrote them `rsid=None, source=authored`, counted them answered, called the change
"moved: the source names a different event", and the recompiled parquets carried `rsid=null`.

Nobody asked is not an answer (`@unreachable-not-absent`), and a re-derivation replaces only what was
answered (`@rederive-never-shortens`). With no reverse map read, the recorded row is carried forward
unchanged, so the module compiles to the same bytes it did before the re-derivation.
"""

import csv
import shutil
from pathlib import Path

import polars as pl
import pytest
from just_dna_compiler.compiler import compile_module
from just_dna_enricher.enrich import enrich
from just_dna_format.manifest import read_manifest

#: "No snapshot" means no ambient one either: a developer's cache base would answer for a missing lane.
pytestmark = pytest.mark.usefixtures("no_ambient_caches")

_EXAMPLE = Path(__file__).parents[2] / "reference_examples" / "hfe_hemochromatosis"
#: The columns a carried row must keep: the back-filled identity and the provenance that names it.
_KEPT = ("rsid", "source", "authority", "status", "source_release", "rsid_alternates")


def _rows(spec: Path) -> list[dict[str, str]]:
    with (spec / "resolution.csv").open(newline="") as handle:
        return list(csv.DictReader(handle))


def _positional(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    """The coordinate-only subjects: their key is the VRS id, never the rsID they were back-filled with."""
    return {row["variant_key"]: row for row in rows if row["variant_key"] != row["rsid"]}


def _rederive(spec: Path, nowhere: Path):
    return _rederive_with(spec, nowhere)


def _rederive_with(spec: Path, nowhere: Path, **caches: Path):
    options = {
        "ensembl_cache": nowhere,
        "clinvar_cache": nowhere,
        "clinvar_gkm_cache": nowhere,
        "pubmind_cache": nowhere,
        "civic_cache": nowhere,
    }
    options.update(caches)
    return enrich(
        spec,
        rederive=True,
        offline=True,
        download=False,
        use_gnomad=False,
        verify_ref=False,
        verify_rsids=False,
        verify_clinsig=False,
        verify_datasets=False,
        **options,
    )


def test_a_rederive_with_no_reverse_map_keeps_the_back_filled_rsid(tmp_path: Path) -> None:
    pristine = tmp_path / "pristine"
    shutil.copytree(_EXAMPLE, pristine)
    spec = tmp_path / "hfe"
    shutil.copytree(_EXAMPLE, spec)
    recorded = _positional(_rows(spec))
    # The fixture is the case: back-filled rows, every one naming the rsID a map gave it.
    assert recorded and all(row["rsid"] for row in recorded.values())

    result = _rederive(spec, tmp_path / "nowhere")

    fresh = _positional(_rows(spec))
    assert set(fresh) == set(recorded)
    for key, row in recorded.items():
        assert {c: fresh[key][c] for c in _KEPT} == {c: row[c] for c in _KEPT}, key
    # Carried, so not compared: a subject nothing re-asked is no drift (`skip=carried_keys`).
    assert all(d.variant_key not in recorded for d in result.rederived or ())

    before = compile_module(pristine, tmp_path / "out-before", strict=True)
    after = compile_module(spec, tmp_path / "out-after", strict=True)
    assert before.success, before.errors
    assert after.success, after.errors
    one = read_manifest(tmp_path / "out-before" / "manifest.json")
    two = read_manifest(tmp_path / "out-after" / "manifest.json")
    assert one.artifact.digest == two.artifact.digest
    # What the audit saw ship: the artifact's rsID for those rows, read off the parquet itself.
    weights = pl.read_parquet(tmp_path / "out-after" / "weights.parquet")
    shipped = weights.filter(pl.col("variant_key").is_in(list(recorded)))
    assert shipped.height and shipped["rsid"].null_count() == 0


def test_a_reverse_map_that_was_read_and_names_no_rsid_still_replaces(tmp_path: Path) -> None:
    """The other half: a map read this run that has no rsID at the allele is an answer, and it replaces.

    The snapshot holds chromosome 6 without `rs773443949`'s locus, so the re-derivation asked and the
    source said nothing is there: the row goes out `authored` with no rsID, and the drift names it.
    Without this, "never replace a back-fill" would pass the test above too.
    """
    spec = tmp_path / "hfe"
    shutil.copytree(_EXAMPLE, spec)
    recorded = _positional(_rows(spec))
    snapshot = tmp_path / "ens"
    (snapshot / "data").mkdir(parents=True)
    pl.DataFrame(
        {"id": ["rs1800562"], "chrom": ["6"], "start": [26092913], "ref": ["G"], "alt": ["A"]}
    ).write_parquet(snapshot / "data" / "homo_sapiens-chr6.parquet")

    result = enrich(
        spec,
        rederive=True,
        offline=True,
        download=False,
        ensembl_cache=snapshot,
        clinvar_cache=tmp_path / "nowhere",
        clinvar_gkm_cache=tmp_path / "nowhere",
        pubmind_cache=tmp_path / "nowhere",
        civic_cache=tmp_path / "nowhere",
        use_gnomad=False,
        verify_ref=False,
        verify_rsids=False,
        verify_clinsig=False,
        verify_datasets=False,
    )

    fresh = _positional(_rows(spec))
    assert {key: (row["rsid"], row["source"]) for key, row in fresh.items()} == dict.fromkeys(
        recorded, ("", "authored")
    )
    assert {d.variant_key for d in result.rederived or ()} >= set(recorded)


def test_a_clinvar_map_read_alone_does_not_answer_for_an_ensembl_back_fill(tmp_path: Path) -> None:
    """The realistic way in: the 14.5 GB Ensembl pull failed and the ClinVar snapshot is there. ClinVar's
    map was read and has nothing at the allele, but the recorded rsID came from Ensembl's, which was not
    read, so it was not re-asked and is carried (the code review of RM393, 2026-11-05)."""
    pristine = tmp_path / "pristine"
    shutil.copytree(_EXAMPLE, pristine)
    spec = tmp_path / "hfe"
    shutil.copytree(_EXAMPLE, spec)
    recorded = _positional(_rows(spec))
    assert {row["source"] for row in recorded.values()} == {"cache"}
    clinvar = tmp_path / "clinvar"
    (clinvar / "data").mkdir(parents=True)
    pl.DataFrame(
        {"rsid": ["rs1800562"], "chrom": ["6"], "start": [26092913], "ref": ["G"], "alt": ["A"]}
    ).write_parquet(clinvar / "data" / "c.parquet")

    _rederive_with(spec, tmp_path / "nowhere", clinvar_cache=clinvar)

    fresh = _positional(_rows(spec))
    for key, row in recorded.items():
        assert {c: fresh[key][c] for c in _KEPT} == {c: row[c] for c in _KEPT}, key
