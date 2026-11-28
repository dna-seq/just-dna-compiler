"""RM350 through the operator's commands, the client boundary, and the on-disk attestation."""

import csv
import hashlib
import json
import shutil
from pathlib import Path

import httpx
import pytest
from just_dna_compiler.compiler import compile_module, reverse_module
from just_dna_compiler.draft import stub_template
from just_dna_enricher import ipd_imgt_hla
from just_dna_enricher import ipd_imgt_hla_build as builder
from just_dna_enricher.caches import LANES_BY_NAME
from just_dna_enricher.cli import app
from just_dna_enricher.enrich import enrich
from just_dna_enricher.licensing import IPD_IMGT_HLA_TERMS, read_sources_file, write_sources_csv
from just_dna_format.snapshot import SNAPSHOT_DATA_DIRNAME, read_release
from just_dna_format.vocab import TEMPLATE_PLACEHOLDER
from typer.testing import CliRunner

LANE = "ipd_imgt_hla"
EXAMPLE = Path(__file__).resolve().parents[2] / "reference_examples" / "hla_alleles"
LABEL = "ipd_imgt_hla_3.66.0"


def build(out: Path, files: Path) -> None:
    cmd = [
        "cache",
        "rebuild",
        "--only",
        LANE,
        "--out",
        str(out.parent),
        "--source",
        f"{LANE}={files / 'Allelelist.txt'}",
        "--pin",
        f"{LANE}=3.66.0",
    ]
    result = CliRunner().invoke(app, cmd)
    assert result.exit_code == 0, result.output


def records(spec: Path) -> list[dict]:
    (path,) = spec.rglob("verification.json")
    return [r for r in json.loads(path.read_text())["records"] if r["check"] == "hla_allele_assignment"]


def test_operator_build_status_and_terms(
    ipd_files: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / LANE
    build(out, ipd_files)
    release = read_release(out)
    assert release.dataset == LABEL
    expected = {p.name: p.read_bytes() for p in ipd_files.glob("*.txt")}
    assert {p.name: p.read_bytes() for p in (out / SNAPSHOT_DATA_DIRNAME).iterdir()} == expected
    assert release.source_sha256 == {
        k: "sha256:" + hashlib.sha256(v).hexdigest() for k, v in expected.items()
    }
    lane = LANES_BY_NAME[LANE]
    assert lane.publish_repo is None and "mirror" in lane.unpublished
    monkeypatch.setenv(lane.env_var, str(out))
    result = CliRunner().invoke(app, ["cache", "status"])
    assert result.exit_code == 0, result.output
    (line,) = [s for s in result.output.splitlines() if s.strip().startswith(LANE)]
    assert "present" in line and LABEL in line and lane.unpublished in line
    (out / SNAPSHOT_DATA_DIRNAME / "Deleted_alleles.txt").unlink()
    assert lane.resolve() is None


@pytest.mark.parametrize("mode", ["best_effort", "strict"])
def test_enrich_outcomes_and_attribution(
    mode: str,
    ipd_files: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    spec = tmp_path / "spec"
    shutil.copytree(EXAMPLE, spec)
    out = tmp_path / LANE
    build(out, ipd_files)
    monkeypatch.setenv("JUST_DNA_IPD_IMGT_HLA_CACHE", str(out))
    table = spec / "allele_function.csv"
    with table.open() as stream:
        reference = {r["gene"][4:] + r["allele"] for r in csv.DictReader(stream)}
    assigned = reference | {"A*02:01:09:01", "A*11:03:07L", "A*11:03L"}
    deleted = {"A*03:12"}
    absent = {"A*04:01", "A*11:03N", "A*03:12:01"}
    table.write_text(
        "gene,allele\n"
        + "".join(f"HLA-{n.split('*')[0]},*{n.split('*')[1]}\n" for n in sorted(assigned | deleted | absent))
        + "APOE,e4\n"
    )
    for _ in range(2):
        caplog.clear()
        enrich(spec, offline=True, mode=mode)
        (rec,) = records(spec)
        assert (rec["subjects"], rec["findings"], rec["release"]) == (
            len(assigned | deleted | absent),
            len(deleted | absent),
            LABEL,
        )
        assert "allele_function.csv" in rec["detail"]
        logs = [r.getMessage() for r in caplog.records]
        (missing,) = [s for s in logs if "not assigned in release" in s]
        (withdrawn,) = [s for s in logs if "deleted HLA allele" in s]
        assert missing.startswith(f"hla_allele_not_assigned: {len(absent)} HLA allele")
        assert set(missing.rsplit(": ", 1)[1].split(", ")) == absent
        assert withdrawn.startswith(f"hla_allele_deleted: {len(deleted)} deleted HLA allele")
        assert LABEL in missing
        assert "Renamed, after review" in withdrawn and all(name in withdrawn for name in deleted)
        rows = [r for r in read_sources_file(spec) if r.source == LANE]
        (row,) = rows
        assert row.layer == "annotation" and row.commercial_use is True
        assert (
            row.redistribution is True
            and row.dataset == LABEL
            and row.notice is not None
            and all(f"Paper {p}" in row.notice for p in "ABC")
            and "FUNDING" not in row.notice
            and "mirroring" in row.notice
        )


@pytest.mark.parametrize("has_names", [True, False])
def test_offline_absence_and_empty_roster(has_names: bool, tmp_path: Path, no_ambient_caches: Path) -> None:
    spec = tmp_path / "spec"
    shutil.copytree(EXAMPLE, spec)
    if not has_names:
        (spec / "allele_function.csv").write_text("gene,allele\nAPOE,e4\n")
    enrich(spec, offline=True)
    if has_names:
        (rec,) = records(spec)
        assert "allele_function.csv" in rec["detail"]
        assert rec["skipped"] == "offline" and "could not ask" in rec["detail"]
        assert "not assigned" not in rec["detail"] and rec["release"] is None
    else:
        assert records(spec) == []
    assert LANE not in {r.source for r in read_sources_file(spec)}


@pytest.mark.parametrize("failure", ["version", "wrong header", "extra field", "truncated", "410"])
def test_failed_second_file_preserves_the_snapshot(failure: str, ipd_files: Path, tmp_path: Path) -> None:
    out = tmp_path / LANE
    build(out, ipd_files)
    before = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}

    def upstream(request: httpx.Request) -> httpx.Response:
        name = request.url.path.split("/")[-1]
        assert request.url.path.startswith("/ANHIG/IMGTHLA/v3.66.0-alpha/")
        body = (ipd_files / name).read_bytes()
        if name == "Deleted_alleles.txt":
            if failure == "410":
                return httpx.Response(410)
            if failure == "version":
                body = body.replace(b"3.66.0", b"3.65.0")
            if failure == "wrong header":
                body = b"<html>retired</html>"
            if failure == "extra field":
                body += b"HLA93000,A*32:11,unexpected,field\n"
            if failure == "truncated":
                body = body.split(b"HLA92001")[0]
        return httpx.Response(200, content=body)

    for target in (tmp_path / "fresh", out):
        with pytest.raises(builder.IpdHlaUnavailable):
            builder.build_snapshot(target, transport=httpx.MockTransport(upstream))
        actual = {p.relative_to(target): p.read_bytes() for p in target.rglob("*") if p.is_file()}
        assert actual == (before if target == out else {})


@pytest.mark.parametrize(
    "response,attempts", [(404, 1), (410, 1), (403, 1), (200, 1), (429, 2), (503, 2), ("transport", 2)]
)
def test_client_retry_and_error_contract(response: int | str, attempts: int, ipd_files: Path) -> None:
    calls: list[str] = []

    def upstream(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if len(calls) == 1:
            if response == "transport":
                raise httpx.ReadError("connection lost", request=request)
            return httpx.Response(response, content=b"unexpected HTML")
        return httpx.Response(200, content=(ipd_files / "Allelelist.txt").read_bytes())

    client = builder.IpdHlaClient(transport=httpx.MockTransport(upstream))
    if attempts == 1:
        with pytest.raises(builder.IpdHlaUnavailable) as exc:
            client.fetch("3.66.0", "Allelelist.txt")
        assert isinstance(exc.value, builder.IpdHlaRetired) == (response in (404, 410))
    else:
        assert client.fetch("3.66.0", "Allelelist.txt") == (ipd_files / "Allelelist.txt").read_bytes()
    assert len(calls) == attempts


@pytest.mark.parametrize("use", ["unstated", "commercial", "non_commercial"])
def test_pull_from_curators_once_per_host(
    use: str,
    no_ambient_caches: Path,
    ipd_files: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []

    def serve(_transport: httpx.HTTPTransport, req: httpx.Request) -> httpx.Response:
        calls.append(str(req.url))
        return httpx.Response(200, content=(ipd_files / req.url.path.split("/")[-1]).read_bytes())

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", serve)
    cmd = ["cache", "pull", "--only", LANE, "--use", use]
    for _ in range(2):
        result = CliRunner().invoke(app, cmd)
        assert result.exit_code == 0, result.output
    root = "https://raw.githubusercontent.com/ANHIG/IMGTHLA/v3.66.0-alpha/"
    assert sorted(calls) == sorted(root + p.name for p in ipd_files.iterdir())
    assert LANES_BY_NAME[LANE].resolve() is not None


def test_builder_command_accepts_a_pin_and_rejects_latest(ipd_files: Path, tmp_path: Path) -> None:
    cmd = [
        "ipd-imgt-hla",
        "build",
        "--out",
        str(tmp_path / "cache"),
        "--source",
        str(ipd_files / "Allelelist.txt"),
    ]
    built = CliRunner().invoke(app, [*cmd, "--pin", "3.66.0"])
    assert built.exit_code == 0 and LABEL in built.output, built.output
    refused = CliRunner().invoke(app, [*cmd, "--pin", "Latest"])
    assert refused.exit_code != 0 and "release" in refused.output


def test_enrich_cli_reports_assigned_and_pins_verbatim_notice(
    ipd_files: Path,
    tmp_path: Path,
    no_ambient_caches: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / LANE
    build(out, ipd_files)
    monkeypatch.setenv(LANES_BY_NAME[LANE].env_var, str(out))
    spec = tmp_path / "spec"
    shutil.copytree(EXAMPLE, spec)
    result = CliRunner().invoke(app, ["enrich", str(spec), "--strict", "--offline"])
    assert result.exit_code == 0, result.output
    with (spec / "allele_function.csv").open() as stream:
        names = {row["gene"][4:] + row["allele"] for row in csv.DictReader(stream)}
    (line,) = [s for s in result.output.splitlines() if "assigned HLA allele name(s)" in s]
    assert line.startswith(f"{len(names)} assigned") and all(name in line for name in names)
    (row,) = [r for r in read_sources_file(spec) if r.source == LANE]
    assert row.license_sha256 == read_release(out).license_sha256


def test_both_headers_must_agree_with_the_pin(ipd_files: Path, tmp_path: Path) -> None:
    for table in ipd_files.glob("*.txt"):
        table.write_bytes(table.read_bytes().replace(b"3.66.0", b"3.65.0"))
    result = CliRunner().invoke(
        app,
        [
            "ipd-imgt-hla",
            "build",
            "--source",
            str(ipd_files / "Allelelist.txt"),
            "--out",
            str(tmp_path / "out"),
            "--pin",
            "3.66.0",
        ],
    )
    assert result.exit_code != 0 and "3.65.0" in result.output and "3.66.0" in result.output


def test_the_lane_is_documented_with_its_override() -> None:
    root = EXAMPLE.parents[1]
    lane = LANES_BY_NAME[LANE]
    assert f"# {lane.env_var}=" in (root / ".env.template").read_text().splitlines()
    assert any(
        f"`${lane.env_var}`" in line and f"`{lane.ensure.__name__}`" in line
        for line in (root / "docs/ENRICHER.md").read_text().splitlines()
    )


def test_checked_hla_module_round_trips(
    ipd_files: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / LANE
    build(out, ipd_files)
    monkeypatch.setenv(LANES_BY_NAME[LANE].env_var, str(out))
    spec = tmp_path / "spec"
    shutil.copytree(EXAMPLE, spec)
    enrich(spec, offline=True)
    original = compile_module(spec, tmp_path / "first", strict=True)
    assert original.success, original.errors
    reverse_module(tmp_path / "first", tmp_path / "reverse")
    rebuilt = compile_module(tmp_path / "reverse", tmp_path / "second", strict=True)
    assert rebuilt.success, rebuilt.errors
    assert rebuilt.manifest.artifact.digest == original.manifest.artifact.digest
    assert rebuilt.manifest.content_signature == original.manifest.content_signature
    reversed_spec = tmp_path / "reverse"
    assert read_sources_file(reversed_spec) == read_sources_file(spec)
    enrich(reversed_spec, offline=True)
    for key in ("subjects", "findings", "release", "detail"):
        assert records(reversed_spec)[0][key] == records(spec)[0][key]


def test_online_enrich_provisions_under_the_modules_declaration(
    ipd_files: Path,
    tmp_path: Path,
    no_ambient_caches: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    out = tmp_path / LANE
    build(out, ipd_files)
    uses: list[str] = []

    def provision(*, declared_use: str = "unstated") -> Path:
        uses.append(declared_use)
        return out

    monkeypatch.setattr(ipd_imgt_hla, "ensure_ipd_imgt_hla_snapshot", provision)
    spec = tmp_path / "spec"
    shutil.copytree(EXAMPLE, spec)
    write_sources_csv([IPD_IMGT_HLA_TERMS.row("annotation", declared_use="commercial")], spec / "sources.csv")
    enrich(spec, verify_datasets=False, mint_vrs=False, verify_ref=False)
    (row,) = [r for r in read_sources_file(spec) if r.source == LANE]
    # The author's own row wins the merge; the run never rewrites its notice.
    assert row.declared_use == "commercial" and row.notice == IPD_IMGT_HLA_TERMS.notice
    assert uses == ["commercial"]
    assert records(spec)[0]["release"] == LABEL


def test_a_later_section_of_the_deleted_list_is_read_as_withdrawn(ipd_files: Path) -> None:
    # The real Deleted_alleles.txt (3.66.0) carries a second `#` section with its own header row,
    # "# Alleles With Suffix Changes". Found by the lead's live build of 2026-11-28, which refused
    # the whole file at that line.
    data = (ipd_files / "Deleted_alleles.txt").read_bytes()
    _, withdrawn = builder._read_table(data, "Deleted_alleles.txt")
    assert "A*01:159" in withdrawn and "A*01:159Q" in withdrawn["A*01:159"]
    assert "A*03:12" in withdrawn, "the first section is still read"


def test_a_section_line_must_be_followed_by_the_header(ipd_files: Path) -> None:
    path = ipd_files / "Deleted_alleles.txt"
    path.write_text(
        path.read_text(encoding="utf-8").replace("Changes\nAlleleID,Allele,Description\n", "Changes\n")
    )
    with pytest.raises(builder.IpdHlaUnavailable, match="after a section line"):
        builder._read_table(path.read_bytes(), "Deleted_alleles.txt")


def test_section_at_end_of_deleted_list_is_incomplete(ipd_files: Path) -> None:
    path = ipd_files / "Deleted_alleles.txt"
    with pytest.raises(builder.IpdHlaUnavailable, match="after a section line"):
        builder._read_table(path.read_bytes() + b"# New section\n", path.name)


@pytest.mark.parametrize("gene", ["HLA-a", "hla-A"])
def test_mixed_case_gene_is_assigned(
    gene: str, ipd_files: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / LANE
    build(out, ipd_files)
    monkeypatch.setenv(LANES_BY_NAME[LANE].env_var, str(out))
    allele = next(
        name.partition("*")[2] for name in sorted(builder.load_lists(out).assigned) if name.startswith("A*")
    )
    (tmp_path / "allele_function.csv").write_text(f"gene,allele\n{gene},*{allele}\n")
    enrich(tmp_path, offline=True)
    (record,) = records(tmp_path)
    assert record["findings"] == 0 and f"A*{allele}" in record["detail"]


@pytest.mark.parametrize("table", ["allele_function.csv", "repeat_alleles.csv"])
@pytest.mark.parametrize("mode", ["best_effort", "strict"])
def test_scaffold_withholds_only_its_pass(
    table: str, mode: str, tmp_path: Path, no_ambient_caches: Path
) -> None:
    (tmp_path / table).write_text(stub_template(table))
    if table == "allele_function.csv":
        (tmp_path / "repeat_alleles.csv").write_text(
            "gene,repeat_unit,conclusion,measure_min\nHTT,CAG,HD,1\n"
        )
    else:
        shutil.copy(EXAMPLE / "allele_function.csv", tmp_path)
    result = enrich(tmp_path, offline=True, mode=mode)
    (hla,) = records(tmp_path)
    grades = result.repeat_grades
    if table == "allele_function.csv":
        assert hla["skipped"] == "unsupported" and result.hla_assignment.findings is None
        assert grades.could_not_ask == [("HTT", "CAG")]
        why = hla["detail"]
    else:
        assert hla["skipped"] == "offline" and not grades.covered and not grades.missing
        why = grades.reason
    assert table in why and TEMPLATE_PLACEHOLDER in why
