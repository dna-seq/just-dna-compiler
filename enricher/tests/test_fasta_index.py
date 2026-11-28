"""The index a host writes must support the same random reads as the samtools fixture."""

import gzip
import os
import shutil
import tracemalloc
from pathlib import Path

import pytest
from ga4gh.core import digests
from just_dna_enricher import fasta
from just_dna_enricher.cli import app
from just_dna_format.vrs import REFGET_GRCh38
from typer.testing import CliRunner

_MT = next((Path(__file__).resolve().parents[2] / "assets/grch38_mt_fasta").glob("*.fa"))


def test_write_index_matches_samtools_and_reads_mt(tmp_path: Path) -> None:
    path = tmp_path / _MT.name
    shutil.copyfile(_MT, path)
    index = Path(f"{path}.fai")
    original = Path(f"{_MT}.fai").read_bytes()
    index.write_bytes(original)
    uri = "fasta+" + path.as_uri()
    expected = fasta.FastaReference(uri).get_sequence(REFGET_GRCh38["MT"])
    index.write_text("old index\n")
    for _ in range(2):
        assert fasta.write_fasta_index(path) == index
        assert index.read_bytes() == original
        assert fasta.FastaReference(uri).get_sequence(REFGET_GRCh38["MT"]) == expected


@pytest.mark.parametrize("endings", [(b"\n", b"\r\n"), (b"\r\n", b"\n")])
def test_write_index_multicontig(
    tmp_path: Path, endings: tuple[bytes, bytes], monkeypatch: pytest.MonkeyPatch
) -> None:
    records = {"2": [b"acGT", b"CTAC", b"TG"], "1": [b"TGC", b"GAC", b"T"]}
    path = tmp_path / "wrapped.fa"
    expected_rows = []
    with path.open("wb") as stream:
        for (name, lines), newline in zip(records.items(), endings, strict=True):
            separator = "\t" if name == "2" else "\u2028"
            stream.write(f">{name}{separator}description é".encode() + newline)
            offset = stream.tell()
            sequence = b"".join(lines).upper()
            expected_rows.append(
                [name, str(len(sequence)), str(offset), str(len(lines[0])), str(len(lines[0]) + len(newline))]
            )
            stream.write(newline.join(lines))
            if name == "2":
                stream.write(newline)
            accession = "SQ." + digests.sha512t24u(sequence)
            monkeypatch.setitem(REFGET_GRCh38, name, accession)
            monkeypatch.setitem(fasta._CHROM, accession, name)
    index = fasta.write_fasta_index(path)
    assert [line.split("\t") for line in index.read_text().splitlines()] == expected_rows
    reader = fasta.FastaReference("fasta+" + path.as_uri())
    for name, lines in records.items():
        sequence = b"".join(lines).decode().upper()
        for start, end in ((0, 1), (2, 6), (len(sequence) - 2, len(sequence)), (0, len(sequence))):
            assert reader.get_sequence(REFGET_GRCh38[name], start, end) == sequence[start:end]


@pytest.mark.parametrize(
    ("content", "name", "line", "reason"),
    [
        (gzip.compress(b">MT\nAA\n", mtime=0), None, 1, "compressed"),
        (b">scaffold\nAAAA\nCC\nG\n", "scaffold", 3, "wrap"),
        (b">scaffold\nAAA\nGGGG\n", "scaffold", 3, "wrap"),
        (b">scaffold\nAAA\nCC\r\n", "scaffold", 3, "ending"),
        (b">scaffold\nAAA\r\nCC\n", "scaffold", 3, "ending"),
        (b">scaffold\nAA\n\nC\n", "scaffold", 3, "empty"),
        (b">scaffold\nA\n>scaffold another description\nG\n", "scaffold", 3, "duplicate"),
        (b">MT\nA\n>NC_012920.1\nG\n", "NC_012920.1", 3, "ambiguous"),
        (b">scaffold\nA C\n", "scaffold", 2, "whitespace"),
        (b">scaffold\nA\xff\n", "scaffold", 2, "ASCII"),
        (b">\xff\nA\n", None, 1, "name"),
        (b"ACGT\n", None, 1, "header"),
        (b"", None, 1, "header"),
        (b"> \t\nAA\n", None, 1, "name"),
        (b">MT\n>scaffold\nA\n", "MT", 1, "no sequence"),
        (b">scaffold\n", "scaffold", 1, "no sequence"),
        (b">scaffold\nAA\rCC\n", "scaffold", 2, "ending"),
    ],
)
def test_write_index_refuses_before_replacement(
    tmp_path: Path, content: bytes, name: str | None, line: int, reason: str
) -> None:
    path = tmp_path / "source.fa"
    path.write_bytes(content)
    index = Path(f"{path}.fai")
    old_index = Path(f"{_MT}.fai").read_bytes()
    for existing in (False, True):
        if existing:
            index.write_bytes(old_index)
        with pytest.raises(fasta.FastaConfigurationError) as caught:
            fasta.write_fasta_index(path)
        message = str(caught.value)
        assert f"line {line}" in message and reason in message
        assert (name or "contig") in message
        assert set(tmp_path.iterdir()) == ({path, index} if existing else {path})
        if existing:
            assert index.read_bytes() == old_index


def test_write_index_rename_failure_preserves_old_index(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / _MT.name
    shutil.copyfile(_MT, path)
    index = Path(f"{path}.fai")
    index.write_text("old index\n")

    def fail_replace(source: str | Path, target: str | Path) -> None:
        part = Path(source)
        assert part.parent == index.parent and part.suffix == ".part"
        assert Path(target) == index and part.read_bytes() == Path(f"{_MT}.fai").read_bytes()
        raise OSError("rename failed")

    monkeypatch.setattr(os, "replace", fail_replace)
    with pytest.raises(fasta.FastaConfigurationError, match="rename failed"):
        fasta.write_fasta_index(path)
    assert index.read_text() == "old index\n"
    assert set(tmp_path.iterdir()) == {index, path}


def test_write_index_bounds_memory_on_unwrapped_sequence(tmp_path: Path) -> None:
    path = tmp_path / "unwrapped.fa"
    header = b">scaffold " + b"description " * 700000 + b"\n"
    block = b"ACGT" * 65536
    with path.open("wb") as stream:
        stream.write(header)
        for _ in range(32):
            stream.write(block)
    length = path.stat().st_size - len(header)
    tracemalloc.start()
    try:
        index = fasta.write_fasta_index(path)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert peak < length
    assert index.read_text().split() == ["scaffold", str(length), str(len(header)), str(length), str(length)]


def test_fasta_index_cli(tmp_path: Path) -> None:
    path = tmp_path / "local reference.fa"
    path.write_bytes(b">MT\nAC\n>scaffold\nT\n")
    result = CliRunner().invoke(app, ["fasta", "index", str(path)])
    assert result.exit_code == 0, result.output
    index = Path(f"{path}.fai")
    names = {line[1:].decode() for line in path.read_bytes().splitlines() if line.startswith(b">")}
    assert {row.split("\t")[0] for row in index.read_text().splitlines()} == names
    assert str(index) in result.output and f"{len(names)} contigs" in result.output


def test_fasta_index_cli_reports_bad_input(tmp_path: Path) -> None:
    path = tmp_path / "bad.fa"
    path.write_bytes(b">scaffold\n\n")
    result = CliRunner().invoke(app, ["fasta", "index", str(path)])
    assert result.exit_code != 0
    assert "scaffold" in result.output and "line 2" in result.output


def test_write_index_refuses_compressed_suffix(tmp_path: Path) -> None:
    path = tmp_path / "plain.fa.bgz"
    path.write_bytes(b">MT\nAA\n")
    with pytest.raises(fasta.FastaConfigurationError, match="compressed"):
        fasta.write_fasta_index(path)
    assert set(tmp_path.iterdir()) == {path}


def test_write_index_crlf_split_across_read_buffers(tmp_path: Path) -> None:
    path = tmp_path / "wide.fa"
    header = b">scaffold\n"
    sequence = b"A" * (1024 * 1024 - 1)
    path.write_bytes(header + sequence + b"\r\nT\r\n")
    index = fasta.write_fasta_index(path)
    assert index.read_text().split() == [
        "scaffold",
        str(len(sequence) + 1),
        str(len(header)),
        str(len(sequence)),
        str(len(sequence) + 2),
    ]
