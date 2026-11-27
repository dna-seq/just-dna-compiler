"""A local reference must earn the GRCh38 accession before any caller can read it (RM385)."""

import gzip
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import polars as pl
import pytest
from ga4gh.core import digests
from just_dna_compiler.compiler import load_csv_rows
from just_dna_enricher.cli import app
from just_dna_enricher.enrich.orchestration import _grch38_window
from just_dna_enricher.sequences import (
    SequenceProxy,
    held_by_one_run,
    left_normalize,
    verify_reference_alleles,
)
from just_dna_enricher.vrs import VrsMinter
from just_dna_format.resolution import ResolutionRow
from just_dna_format.verification import read_verification
from just_dna_format.vrs import refget_accession
from typer.testing import CliRunner

_ROOT = Path(__file__).resolve().parents[2]
_FASTA = next((_ROOT / "assets/grch38_mt_fasta").glob("*.fa"))
_MODULE = _ROOT / "reference_examples/mt_common_deletion"


@pytest.fixture
def fasta(tmp_path: Path) -> Path:
    path = tmp_path / "local MT.fa"
    shutil.copyfile(_FASTA, path)
    shutil.copyfile(f"{_FASTA}.fai", f"{path}.fai")
    return path


def _proxy(path: Path, *, offline: bool = True) -> SequenceProxy:
    return SequenceProxy(uri="fasta+" + path.as_uri(), offline=offline)


def _bases(path: Path) -> bytes:
    return b"".join(path.read_bytes().splitlines()[1:]).upper()


def _rows() -> list[ResolutionRow]:
    rows, errors, _ = load_csv_rows(_MODULE / "resolution.csv", ResolutionRow, "resolution.csv")
    assert not errors
    return [row for row in rows if row.vrs_id]


def _mt_deletion() -> tuple[tuple[str, int, str, str], str]:
    alleles = pl.read_parquet(_ROOT / "assets/clinvar_gkm_slice/allele.parquet").to_dicts()
    allele = next(a for a in alleles if a["name"].startswith("NC_012920") and "del" in a["name"])
    spelling = next(e["value"] for e in allele["expressions"] if e["syntax"] == "gnomad")
    chrom, start, ref, alt = spelling.split("-")
    return (chrom, int(start), ref, alt), allele["id"]


def _change_one_base(fasta: Path) -> None:
    header, sep, body = fasta.read_bytes().partition(b"\n")
    fasta.write_bytes(header + sep + (b"A" if body[:1] != b"A" else b"C") + body[1:])


@pytest.mark.parametrize("offline", [True, False])
def test_real_mt_indels_and_ref(fasta: Path, offline: bool) -> None:
    sequences = held_by_one_run(_proxy(fasta, offline=offline))
    accession = refget_accession("chrM")
    bases = _bases(fasta)
    assert accession == "SQ." + digests.sha512t24u(bases)
    assert sequences.subsequence(accession, 57, 124) == bases[57:124].decode()
    rows = _rows()
    check = verify_reference_alleles(rows, sequences=sequences, offline=offline)
    assert (check.subjects, check.not_checked, check.mismatches) == (len(rows), None, [])
    minter = VrsMinter(offline=offline, sequences=sequences)
    window = _grch38_window(sequences.subsequence)
    alleles = pl.read_parquet(_ROOT / "assets/clinvar_gkm_slice/allele.parquet").to_dicts()
    expected = {}
    observed = {}
    for allele in alleles:
        expressions = {e["syntax"]: e["value"] for e in allele["expressions"] or []}
        if not expressions.get("gnomad", "").startswith("MT-"):
            continue
        chrom, pos, ref, alt = expressions["gnomad"].split("-")
        locus = (chrom, int(pos), ref, alt)
        expected[locus] = (allele["id"], "normalized")
        # SPDI supplies an independently recorded right-shifted spelling of the repeat deletion.
        _, start, deleted, inserted = expressions["spdi"].split(":")
        if deleted and inserted:
            assert left_normalize(chrom, int(start) + 1, deleted, inserted, window) == locus
        assert left_normalize(*locus, window) == locus
        observed[locus] = minter.mint(*locus)
    assert expected and observed == expected


@pytest.mark.parametrize(
    ("chrom", "reason"),
    [("MT", "digest mismatch"), ("1", "no such contig"), ("GL000205.2", "outside"), ("MT", "GRCh37")],
)
def test_local_failures_name_contig_in_check_and_minter(fasta: Path, chrom: str, reason: str) -> None:
    build = "GRCh37" if reason == "GRCh37" else "GRCh38"
    if reason == "digest mismatch":
        _change_one_base(fasta)
    sequences = _proxy(fasta)
    row = _rows()[0].model_copy(update={"chrom": chrom, "genome_build": build})
    if build == "GRCh38" and (accession := refget_accession(chrom)):
        assert sequences.subsequence(accession, row.start - 1, row.start) is None
    check = verify_reference_alleles([row], sequences=sequences, offline=True)
    assert check.not_checked == ("unsupported" if build == "GRCh37" else "unreachable")
    assert check.subjects == 0 and not check.mismatches
    detail = " ".join(check.unread_reasons)
    assert chrom in detail and reason in detail
    minter = VrsMinter(sequences=sequences, offline=True)
    assert minter.mint(chrom, row.start, row.ref, row.ref * 2, build=build) == (None, None)
    why = minter.why_not(chrom, row.start, row.ref, row.ref * 2, build=build)
    assert chrom in why and reason in why and "FASTA" in why


@pytest.mark.parametrize("fault", ["missing index", "gzip", "relative"])
def test_bad_configuration_refused_at_build(fasta: Path, fault: str) -> None:
    uri = "fasta+" + fasta.as_uri()
    if fault == "missing index":
        Path(f"{fasta}.fai").unlink()
        match = r"\.fai"
    elif fault == "gzip":
        fasta.write_bytes(gzip.compress(fasta.read_bytes()))
        match = "compressed|gzip"
    else:
        uri = "fasta+file://relative/local.fa"
        match = "absolute"
    with pytest.raises((ValueError, OSError), match=match):
        SequenceProxy(uri=uri, offline=True).proxy()


def test_digests_persist_and_expire(fasta: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    counted = Mock(wraps=digests.sha512t24u)
    monkeypatch.setattr(digests, "sha512t24u", counted)
    bases = _bases(fasta)
    # Lowercase input and the UCSC spelling in the index must bind to the same GRCh38 accession.
    header, sep, body = fasta.read_bytes().partition(b"\n")
    fasta.write_bytes(header.replace(b">MT ", b">chrM ") + sep + body.lower())
    index = Path(f"{fasta}.fai")
    _, length, offset, width, stride = index.read_text().split()
    index.write_text(f"chrM\t{length}\t{int(offset) + 2}\t{width}\t{stride}\n")
    accession = refget_accession("MT")
    proxy = _proxy(fasta)
    with ThreadPoolExecutor(max_workers=4) as pool:
        slices = list(pool.map(lambda i: proxy.subsequence(accession, i, i + 5), range(70)))
    assert slices == [bases[i : i + 5].decode() for i in range(70)]
    assert Path(f"{fasta}.refget.json").is_file()
    assert counted.call_count == 1
    assert _proxy(fasta).subsequence(accession, 5, 8) == bases[5:8].decode()
    assert counted.call_count == 1
    stat = fasta.stat()
    os.utime(fasta, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000_000))
    assert proxy.subsequence(accession, 0, 5) == bases[:5].decode()
    assert counted.call_count == 2


def test_read_only_reference_works_in_memory(
    fasta: Path, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    orig = fasta.parent.stat().st_mode
    fasta.parent.chmod(0o555)
    try:
        if os.access(fasta.parent, os.W_OK):
            monkeypatch.setattr("just_dna_enricher.fasta.atomic_writer", Mock(side_effect=PermissionError))
        counted = Mock(wraps=digests.sha512t24u)
        monkeypatch.setattr(digests, "sha512t24u", counted)
        bases = _bases(fasta)
        for i in (0, 1):
            assert _proxy(fasta).subsequence(refget_accession("MT"), i, i + 1) == bases[i : i + 1].decode()
        assert counted.call_count == 1
        assert not Path(f"{fasta}.refget.json").exists()
        assert len([line for line in caplog.messages if "in memory" in line]) == 1
    finally:
        fasta.parent.chmod(orig)


@pytest.mark.parametrize("uri", ["seqrepo+https://example.invalid", "seqrepo+file:///unused"])
def test_seqrepo_still_switched_off(uri: str, monkeypatch: pytest.MonkeyPatch) -> None:
    builder = Mock(side_effect=AssertionError("offline must not even build seqrepo"))
    monkeypatch.setattr("just_dna_enricher.sequences.create_dataproxy", builder)
    proxy = held_by_one_run(SequenceProxy(uri=uri, offline=True))
    assert proxy.subsequence(refget_accession("MT"), 0, 1) is None
    builder.assert_not_called()


def test_enrich_cli_attests_to_the_answering_source(fasta: Path, no_ambient_caches: Path) -> None:
    spec = fasta.parent / "module"
    shutil.copytree(_MODULE, spec)
    run = CliRunner().invoke(app, ["enrich", str(spec), "--offline", "--sequence-uri", _proxy(fasta).uri])
    assert run.exit_code == 0, (run.output, run.exception)
    record = next(
        r for r in read_verification(spec / "verification.json").records if r.check == "reference_allele"
    )
    assert (record.source, record.witness_source, record.subjects, record.skipped) == (
        "fasta",
        "fasta",
        len(_rows()),
        None,
    )
    assert "FASTA" in run.output and "wrong-build diagnosis" in run.output
    assert "both need a live" not in run.output


def test_unreachable_seqrepo_advice_differs_from_offline(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "just_dna_enricher.sequences.create_dataproxy", Mock(side_effect=OSError("unreachable"))
    )
    minter = VrsMinter()
    assert minter.mint("MT", 7637, "GA", "G") == (None, None)
    assert "unreachable" in minter.why_not("MT", 7637, "GA", "G")
    reason = VrsMinter(offline=True).why_not("MT", 7637, "GA", "G")
    assert "--offline" in reason and "--sequence-uri" in reason


def test_vrs_mint_cli_reads_the_local_indel(fasta: Path) -> None:
    (chrom, start, ref, alt), expected_id = _mt_deletion()
    spelling = f"{chrom}-{start}-{ref}-{alt}"
    spec = fasta.parent / "module"
    shutil.copytree(_MODULE, spec)
    path = spec / "resolution.csv"
    path.write_text(
        f"variant_key,chrom,start,ref,alts,genome_build\n{spelling},{chrom},{start},{ref},{alt},GRCh38\n"
    )
    run = CliRunner().invoke(
        app, ["vrs", "mint", str(spec), "--offline", "--sequence-uri", _proxy(fasta).uri]
    )
    assert run.exit_code == 0, (run.output, run.exception)
    rows, errors, _ = load_csv_rows(path, ResolutionRow, path.name)
    assert not errors and {row.vrs_id for row in rows} == {expected_id}
    record = next(
        r for r in read_verification(spec / "verification.json").records if r.check == "vrs_allele_id"
    )
    assert record.witness_source == "fasta"


def test_built_but_unreachable_sequence_service_names_the_failed_read() -> None:
    service = Mock()
    service.get_metadata.side_effect = ConnectionError("service unreachable")
    minter = VrsMinter(sequences=SequenceProxy(_proxy=service))
    assert minter.mint("MT", 7637, "GA", "G") == (None, None)
    assert "unreachable" in minter.why_not("MT", 7637, "GA", "G")


def test_changed_fasta_cannot_answer_from_a_minters_memo(fasta: Path) -> None:
    minter = VrsMinter(sequences=_proxy(fasta), offline=True)
    locus, expected_id = _mt_deletion()
    assert minter.mint(*locus) == (expected_id, "normalized")
    _change_one_base(fasta)
    assert minter.mint(*locus) == (None, None)
    assert "digest mismatch" in minter.why_not(*locus)


def test_a_partial_ref_at_the_contig_end_is_unread(fasta: Path) -> None:
    bases = _bases(fasta)
    row = _rows()[0].model_copy(update={"start": len(bases), "ref": bases[-2:].decode()})
    check = verify_reference_alleles([row], sequences=_proxy(fasta), offline=True)
    assert (check.not_checked, check.unread, check.mismatches) == ("unreachable", 1, [])
