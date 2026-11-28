"""A local reference must earn the GRCh38 accession before any caller can read it (RM385)."""

import gzip
import hashlib
import os
import shutil
from concurrent.futures import ThreadPoolExecutor
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
from unittest.mock import Mock

import polars as pl
import pytest
from ga4gh.core import digests
from just_dna_compiler.compiler import load_csv_rows
from just_dna_enricher.civic_build import CivicDownload
from just_dna_enricher.civic_draft import CivicDraftResult
from just_dna_enricher.cli import app
from just_dna_enricher.clinvar_gkm_build import GRCH38_ACCESSIONS
from just_dna_enricher.enrich.orchestration import _grch38_window
from just_dna_enricher.fasta import FastaConfigurationError, FastaReference
from just_dna_enricher.pgx_draft import PgxDraftResult, _reference_reader
from just_dna_enricher.sequences import (
    SequenceProxy,
    held_by_one_run,
    left_normalize,
    verify_reference_alleles,
)
from just_dna_enricher.vrs import VrsMinter
from just_dna_format.resolution import ResolutionRow
from just_dna_format.verification import read_verification
from just_dna_format.vrs import REFGET_GRCh38, refget_accession
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


def _mt_with_headers(fasta: Path, headers: list[str]) -> None:
    """Write the real wrapped MT bases under each header, with matching FAI byte offsets."""
    body = fasta.read_bytes().split(b"\n", 1)[1]
    index = Path(f"{fasta}.fai")
    _, length, _, bases, width = index.read_text().split()
    entries = []
    with fasta.open("wb") as stream:
        for header in headers:
            stream.write(f">{header}\n".encode())
            entries.append(f"{header.split()[0]}\t{length}\t{stream.tell()}\t{bases}\t{width}\n")
            stream.write(body)
    index.write_text("".join(entries))


@pytest.mark.parametrize("changed", [False, True], ids=["bound", "digest_mismatch"])
def test_contig_identity_and_local_read_problem(fasta: Path, changed: bool) -> None:
    sequences = _proxy(fasta)
    if changed:
        _change_one_base(fasta)
    digest = "SQ." + digests.sha512t24u(_bases(fasta))
    records = sequences.contig_identity(["chrM", "chr1"])
    assert set(records) == {"MT", "1"}
    mt = records["MT"]
    expected = REFGET_GRCh38["MT"]
    assert (mt.chrom, mt.fasta_name, mt.expected_accession, mt.found_digest) == ("MT", "MT", expected, digest)
    assert mt.status == ("digest_mismatch" if changed else "bound")
    assert (mt.found_digest == mt.expected_accession) == (not changed)
    with pytest.raises(FrozenInstanceError):
        mt.status = "absent"
    with pytest.raises(ValueError, match="status"):
        replace(mt, status="unknown")
    if changed:
        assert sequences.local_read_problem("MT", "GRCh38") == (
            f"local FASTA: MT digest mismatch (found {digest}, expected {expected})"
        )
    else:
        assert sequences.local_read_problem("MT", "GRCh38") == (
            "local FASTA: could not read the requested interval on MT"
        )
    absent = records["1"]
    assert (
        absent.chrom,
        absent.fasta_name,
        absent.expected_accession,
        absent.found_digest,
        absent.status,
    ) == (
        "1",
        None,
        REFGET_GRCh38["1"],
        None,
        "absent",
    )
    assert sequences.local_read_problem("1", "GRCh38") == "local FASTA: no such contig 1"


def test_contig_identity_full_pass_and_cache(fasta: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    counted = Mock(wraps=digests.sha512t24u)
    monkeypatch.setattr(digests, "sha512t24u", counted)
    reader = FastaReference(_proxy(fasta).uri)
    assert set(reader.contig_identity("10")) == {"10"}
    assert reader.contig_identity([]) == {}
    counted.assert_not_called()
    records = reader.contig_identity()
    assert set(records) == set(REFGET_GRCh38)
    assert {chrom for chrom, r in records.items() if r.status == "absent"} == set(REFGET_GRCh38) - {"MT"}
    assert {chrom for chrom, r in records.items() if r.status == "bound"} == {"MT"}
    assert _proxy(fasta).contig_identity() == records
    counted.assert_called_once()
    with pytest.raises(ValueError, match="outside the GRCh38 refget table"):
        reader.contig_identity(["GL000205.2"])


def test_refseq_header_binds_real_mt(fasta: Path) -> None:
    bases = _bases(fasta)
    name = "NC_012920.1"
    _mt_with_headers(fasta, [f"{name} Homo sapiens mitochondrion, complete genome"])
    proxy = _proxy(fasta)
    assert proxy.subsequence(REFGET_GRCh38["MT"], 0, len(bases)) == bases.decode()
    mt = proxy.contig_identity("MT")["MT"]
    assert (mt.fasta_name, mt.status, mt.found_digest) == (name, "bound", "SQ." + digests.sha512t24u(bases))


def test_refseq_header_and_short_name_are_ambiguous(fasta: Path) -> None:
    _mt_with_headers(fasta, ["MT", "NC_012920.1"])
    with pytest.raises(FastaConfigurationError, match="ambiguous .fai entries for MT"):
        _proxy(fasta).proxy()


def test_refseq_header_recognition_is_version_specific(fasta: Path) -> None:
    # Reuse MT sequence under every header. Only MT should bind, though every primary is present.
    _mt_with_headers(fasta, [*GRCH38_ACCESSIONS, "NC_000002.11", "GL000205.2", "KI270728.1"])
    records = _proxy(fasta).contig_identity()
    assert {r.fasta_name: r.chrom for r in records.values()} == GRCH38_ACCESSIONS
    assert {r.chrom for r in records.values() if r.status == "digest_mismatch"} == set(REFGET_GRCh38) - {"MT"}


@pytest.mark.parametrize("uri", ["seqrepo+https://example.invalid", "seqrepo+file:///unused"])
def test_non_fasta_contig_identity_withheld_without_opening_seqrepo(
    uri: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    builder = Mock(side_effect=AssertionError("identity is local FASTA only"))
    monkeypatch.setattr("just_dna_enricher.sequences.create_dataproxy", builder)
    sequences = SequenceProxy(uri=uri)
    assert sequences.contig_identity() is None
    assert sequences.contig_identity([]) is None
    builder.assert_not_called()


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


def test_civic_panel_cli_passes_the_selected_sequence_source(
    fasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft = Mock(return_value=CivicDraftResult())
    monkeypatch.setattr("just_dna_enricher.cli.panel_commands.draft_panel_from_civic", draft)
    uri = _proxy(fasta).uri
    run = CliRunner().invoke(
        app,
        [
            "draft-panel",
            str(fasta.parent),
            "--source",
            "civic",
            "--gene",
            "BRCA1",
            "--sequence-uri",
            uri,
            "--offline",
        ],
    )
    assert run.exit_code == 0, (run.output, run.exception)
    source = draft.call_args.kwargs["sequences"]
    assert (source.uri, source.offline) == (uri, True)


def test_cpic_draft_cli_shares_the_selected_sequence_source(
    fasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    draft = Mock(return_value=PgxDraftResult())
    monkeypatch.setattr("just_dna_enricher.cli.authoring_commands.draft_gene", draft)
    uri = _proxy(fasta).uri
    run = CliRunner().invoke(
        app,
        [
            "draft",
            str(fasta.parent),
            "--gene",
            "CYP2C9",
            "--gene",
            "CYP2C19",
            "--sequence-uri",
            uri,
            "--offline",
        ],
    )
    assert run.exit_code == 0, (run.output, run.exception)
    first, second = (call.kwargs["sequences"] for call in draft.call_args_list)
    assert first is second and (first.uri, first.offline) == (uri, True)


def test_cpic_reads_notation_bases_from_the_local_fasta_offline(fasta: Path) -> None:
    read = _reference_reader(_proxy(fasta), offline=True)
    assert read("MT", 1, 10) == _bases(fasta)[:10].decode()


def test_civic_reproduce_checks_placed_refs_through_the_selected_source(
    fasta: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def download(dest: Path, url: str) -> CivicDownload:
        shutil.copyfile(_ROOT / "assets/civic_slice" / dest.name, dest)
        return CivicDownload(dest, hashlib.sha256(dest.read_bytes()).hexdigest(), url)

    monkeypatch.setattr("just_dna_enricher.civic_build.download_civic_file", download)
    verify = Mock(wraps=verify_reference_alleles)
    monkeypatch.setattr("just_dna_enricher.cli.civic_commands.verify_reference_alleles", verify)
    uri = _proxy(fasta).uri
    run = CliRunner().invoke(
        app,
        [
            "civic",
            "reproduce",
            "--out",
            str(fasta.parent / "reproduce"),
            "--sequence-uri",
            uri,
        ],
    )
    assert run.exit_code == 0, (run.output, run.exception)
    verify.assert_called_once()
    assert verify.call_args.args[0] and verify.call_args.kwargs["sequences"].uri == uri


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
